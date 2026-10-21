from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from collections import defaultdict
import time
import secrets
from app.services.email_service import send_password_reset_email

auth_bp = Blueprint('auth', __name__)
FAILED_LOGIN_ATTEMPTS = defaultdict(lambda: [0, 0.0])

def create_default_superadmin():
    """Create default superadmin if none exists or update email."""
    from app import db
    from app.models.user import User
    admin = User.query.filter_by(role='superadmin').first()
    if not admin:
        admin = User(
            name='Super Admin',
            username='admin',
            role='superadmin',
            email='', # Email is left blank to avoid unwanted notifications
            is_active=True
        )
        initial_password = secrets.token_urlsafe(12)
        admin.set_password(initial_password)
        db.session.add(admin)
        db.session.commit()
        print(f'[OK] Default superadmin created: admin / {initial_password}  (change it after first login)')
    else:
        pass # Do not enforce the email on the superadmin account

@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(_get_dashboard_url(current_user.role))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(_get_dashboard_url(current_user.role))
        
    if request.method == 'POST':
        from app.models.user import User
        from sqlalchemy import func
        username_raw = request.form.get('username', '').strip()
        username = username_raw.lower()
        password = request.form.get('password', '')
        
        # Check lockout status for this username
        attempts, lockout_time = FAILED_LOGIN_ATTEMPTS[username]
        if lockout_time > time.time():
            remaining = int(lockout_time - time.time())
            flash(f'This account is blocked due to 5 failed attempts. Please try again in {remaining} seconds.', 'error')
            return render_template('auth/login.html')
            
        user = User.query.filter(func.lower(User.username) == username).first()
        
        if user and user.is_active and user.check_password(password):
            # Session regeneration to prevent session fixation / cookie theft
            from flask import session
            import uuid
            session.clear()
            session['session_token'] = str(uuid.uuid4())
            session.modified = True
            
            login_user(user)
            # Clear rate limit state on successful login
            FAILED_LOGIN_ATTEMPTS.pop(username, None)
            
            # Log security action
            from app.models.security_log import log_security_action
            log_security_action('login_success', f"User {user.name} logged in successfully.", user_id=user.id, username=user.username)
            
            next_page = request.args.get('next')
            from urllib.parse import urlparse, urljoin
            def is_safe_url(target):
                ref_url = urlparse(request.host_url)
                test_url = urlparse(urljoin(request.host_url, target))
                return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc
            if not next_page or not is_safe_url(next_page):
                next_page = _get_dashboard_url(user.role)
            return redirect(next_page)
        
        # Record failed attempt
        from app.models.security_log import log_security_action
        log_security_action('login_failed', f"Failed login attempt for username: {username_raw}", user_id=user.id if user else None, username=username_raw)
        
        FAILED_LOGIN_ATTEMPTS[username][0] += 1
        failed_count = FAILED_LOGIN_ATTEMPTS[username][0]
        if failed_count >= 5:
            FAILED_LOGIN_ATTEMPTS[username][1] = time.time() + 180 # Lock for 3 mins (180 seconds)
            FAILED_LOGIN_ATTEMPTS[username][0] = 0
            flash('Too many failed attempts. This account is blocked for 3 minutes.', 'error')
        else:
            remaining = 5 - failed_count
            flash(f'Invalid username/password or account inactive. You have {remaining} attempt{"s" if remaining > 1 else ""} remaining before lockout.', 'error')
            
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    from flask import session, make_response, current_app
    # Log security action
    from app.models.security_log import log_security_action
    log_security_action('logout', f"User {current_user.name} logged out.", user_id=current_user.id, username=current_user.username)

    # 1. Clear session dictionary completely on the server-side
    session.clear()
    
    # 2. Logout from Flask-Login (removes active session keys and handles signals)
    logout_user()
    
    flash('You have been logged out successfully.', 'info')
    response = make_response(redirect(url_for('auth.login')))
    
    # 3. Explicitly expire the session cookie in the user's browser
    session_cookie_name = current_app.config.get('SESSION_COOKIE_NAME', 'session')
    response.set_cookie(session_cookie_name, '', expires=0, max_age=0, path='/')
    
    # 4. Explicitly expire the remember_token cookie in the user's browser
    remember_cookie_name = current_app.config.get('REMEMBER_COOKIE_NAME', 'remember_token')
    response.set_cookie(remember_cookie_name, '', expires=0, max_age=0, path='/')
    
    return response

def _get_dashboard_url(role):
    if role == 'superadmin':
        return url_for('dashboard.admin_dashboard')
    elif role == 'manager':
        return url_for('dashboard.manager_dashboard')
    return url_for('dashboard.employee_dashboard')

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    from app import db
    from app.models.user import User
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not name:
            flash('Name is required.', 'error')
            return redirect(url_for('auth.profile'))
            
        # Email uniqueness check if changed
        if email and email != current_user.email:
            existing = User.query.filter(User.email == email, User.id != current_user.id).first()
            if existing:
                flash('This email address is already in use by another account.', 'error')
                return redirect(url_for('auth.profile'))
                
        current_user.name = name
        current_user.email = email
        current_user.phone = phone
        
        if new_password:
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('auth.profile'))
            if len(new_password) < 8:
                flash('Password must be at least 8 characters long.', 'error')
                return redirect(url_for('auth.profile'))
            current_user.set_password(new_password)
            
        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
            
        return redirect(url_for('auth.profile'))
        
    return render_template('auth/profile.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
        
    if request.method == 'POST':
        from app.models.user import User
        from app import db
        from sqlalchemy import func
        
        username = request.form.get('username', '').strip().lower()
        user = User.query.filter(func.lower(User.username) == username).first()
        
        # We always show a generic message to prevent username scanning
        flash('If this username exists, a password reset link has been sent to the registered email address.', 'success')
        
        if user and user.email:
            # Generate secure token
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            
            try:
                db.session.commit()
                base_url = current_app.config['BASE_URL']
                if base_url.endswith('/'):
                    base_url = base_url[:-1]
                reset_url = f"{base_url}/reset-password/{token}"
                # Send email
                send_password_reset_email(
                    to_email=user.email,
                    name=user.name,
                    reset_url=reset_url,
                    company_name=current_app.config['COMPANY_NAME']
                )
            except Exception as e:
                db.session.rollback()
                print(f"[AUTH ERROR] Failed to store or send reset token: {e}")
                
        return redirect(url_for('auth.login'))
        
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
        
    from app.models.user import User
    from app import db
    
    # Find user with valid token and not expired
    user = User.query.filter(
        User.reset_token == token,
        User.reset_token_expiry > datetime.utcnow()
    ).first()
    
    if not user:
        flash('The password reset link is invalid or has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))
        
    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        if not new_password or not confirm_password:
            flash('Both password fields are required.', 'error')
            return render_template('auth/reset_password.html', token=token)
            
        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password.html', token=token)
            
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/reset_password.html', token=token)
            
        try:
            # Set new password
            user.set_password(new_password)
            # Clear reset token
            user.reset_token = None
            user.reset_token_expiry = None
            db.session.commit()
            flash('Your password has been successfully reset! Please sign in with your new password.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'error')
            
    return render_template('auth/reset_password.html', token=token)
