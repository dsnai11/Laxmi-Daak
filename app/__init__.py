from flask import Flask
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, CSRFError
from app.config import Config

db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.url_map.strict_slashes = False
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    # No cors_allowed_origins='*': default only accepts same-origin websocket connections
    socketio.init_app(app, async_mode='threading')
    csrf.init_app(app)
    
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        from flask import flash, redirect, url_for
        flash('Session refreshed. Please click Sign In again.', 'info')
        return redirect(url_for('auth.login'))
        
    with app.app_context():
        # Import models to register them with SQLAlchemy
        from app.models.user import User
        from app.models.branch import Branch
        from app.models.parcel import Parcel
        from app.models.scan_log import ScanLog
        from app.models.item import Item
        from app.models.department import Department
        from app.models.security_log import SecurityLog
        from app.models.state_billing_rate import StateBillingRate
        
        # Create all tables
        db.create_all()

        # Scrub legacy plain-text passwords (idempotent)
        from sqlalchemy import text
        try:
            db.session.execute(text("UPDATE users SET password_plain = NULL WHERE password_plain IS NOT NULL"))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[WARN] Could not scrub password_plain: {e}")

        # Seed default items if empty
        if Item.query.count() == 0:
            default_items = ['Documents / Files', 'Laptop / Computer Parts', 'Clothes / Apparel', 'Medicines / Medical Kits', 'Books / Stationery', 'Electronics / Gadgets', 'Other Packaged Goods']
            for name in default_items:
                db.session.add(Item(name=name))
            db.session.commit()
        
        # Register blueprints
        from app.routes.auth import auth_bp
        from app.routes.dashboard import dashboard_bp
        from app.routes.dispatch import dispatch_bp
        from app.routes.scan import scan_bp
        from app.routes.tracking import tracking_bp
        from app.routes.admin import admin_bp
        from app.routes.reports import reports_bp
        from app.routes.api import api_bp
        
        app.register_blueprint(auth_bp)
        app.register_blueprint(dashboard_bp)
        app.register_blueprint(dispatch_bp)
        app.register_blueprint(scan_bp)
        app.register_blueprint(tracking_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(reports_bp)
        app.register_blueprint(api_bp)
        
        # User loader
        from app.models.user import User
        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))
        
        # Context processor
        @app.context_processor
        def inject_globals():
            from flask_login import current_user
            from datetime import date
            overdue_count = 0
            pending_pickup_count = 0
            pending_confirm_count = 0
            my_queries_count = 0
            incoming_for_user = []
            incoming_alerts_count = 0
            outgoing_alerts_count = 0
            if current_user.is_authenticated:
                try:
                    from sqlalchemy import or_
                    q = Parcel.query.filter(
                        Parcel.due_date != None,
                        Parcel.due_date < date.today(),
                        Parcel.status.in_(['pending', 'in_transit'])
                    ).filter((Parcel.is_archived == False) | (Parcel.is_archived == None))

                    if current_user.role == 'superadmin':
                        pass  # superadmin sees all overdue
                    elif current_user.role == 'manager' and current_user.branch_id:
                        q = q.filter(or_(
                            Parcel.sender_branch_id == current_user.branch_id,
                            Parcel.current_branch_id == current_user.branch_id,
                            Parcel.receiver_branch_id == current_user.branch_id
                        ))
                    else:
                        # Employee: STRICT match — only exact email or exact full name
                        # Never use fuzzy first-name prefix to avoid leaking other users' data
                        strict_conds = [Parcel.created_by == current_user.id]
                        if current_user.email and '@' in current_user.email and len(current_user.email.strip()) > 4:
                            em = current_user.email.strip()
                            strict_conds.append(Parcel.receiver_email.ilike(em))
                            strict_conds.append(Parcel.sender_email.ilike(em))
                        if current_user.name and len(current_user.name.strip()) > 2:
                            nm = current_user.name.strip()
                            strict_conds.append(Parcel.receiver_name.ilike(nm))
                            strict_conds.append(Parcel.sender_name.ilike(nm))
                        q = q.filter(or_(*strict_conds))

                    overdue_count = q.count()
                except Exception as e:
                    print(f"Error calculating overdue_count: {e}")
                    overdue_count = 0
                try:
                    if current_user.role == 'superadmin':
                        pending_pickup_count = Parcel.query.filter_by(status='query_raised').count()
                    else:
                        # my_queries_count: parcels user raised that still need action (query_raised)
                        my_queries_count = Parcel.query.filter_by(
                            created_by=current_user.id, status='query_raised'
                        ).count()
                        # pending_confirm_count: parcels delivered, awaiting user confirmation
                        pending_confirm_count = Parcel.query.filter_by(
                            created_by=current_user.id, status='delivered_pending'
                        ).count()
                except Exception:
                    pass

                # Fetch incoming parcels for this user (matching ONLY exact email or receiver name - NEVER dummy phones)
                try:
                    email_clean = current_user.email.strip() if current_user.email else None
                    name_clean = current_user.name.strip() if current_user.name else None
                    username_clean = current_user.username.strip() if current_user.username else None

                    filters = []
                    if email_clean and '@' in email_clean and len(email_clean) > 4:
                        filters.append(Parcel.receiver_email.ilike(email_clean))
                    if name_clean and len(name_clean) > 2:
                        filters.append(Parcel.receiver_name.ilike(name_clean))
                        parts = name_clean.split()
                        if len(parts) > 1 and len(parts[0]) >= 4:
                            filters.append(Parcel.receiver_name.ilike(f"{parts[0]}%"))
                    if username_clean and len(username_clean) > 2:
                        filters.append(Parcel.receiver_name.ilike(username_clean))

                    if filters:
                        from sqlalchemy import or_
                        found_parcels = Parcel.query.filter(
                            or_(*filters),
                            Parcel.status.in_(['pending', 'in_transit', 'query_raised', 'picked_up', 'delivered_pending'])
                        ).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).order_by(Parcel.dispatched_at.desc()).all()
                        for p in found_parcels:
                            p.user_alert_type = 'incoming'
                        incoming_for_user = found_parcels
                        incoming_alerts_count = len(found_parcels)
                except Exception as e:
                    print(f"Error fetching incoming user parcels: {e}")
            from app.models.branch import Branch
            branches = Branch.query.order_by(Branch.name).all() if current_user.is_authenticated else []
            return dict(
                current_user=current_user,
                company_name=app.config['COMPANY_NAME'],
                overdue_count=overdue_count,
                today=date.today(),
                all_branches=branches,
                pending_pickup_count=pending_pickup_count,
                pending_confirm_count=pending_confirm_count,
                my_queries_count=my_queries_count,
                incoming_for_user=incoming_for_user,
                incoming_alerts_count=incoming_alerts_count,
                outgoing_alerts_count=outgoing_alerts_count,
            )
        
        # Create default superadmin
        from app.routes.auth import create_default_superadmin
        create_default_superadmin()
        
        # Start background checkers for overdue and missing fields
        from app.services.email_service import start_overdue_checker, start_missing_fields_checker
        start_overdue_checker(app)
        start_missing_fields_checker(app)
        
    @app.before_request
    def verify_session_binding():
        from flask_login import current_user, logout_user
        from flask import session, request, redirect, url_for, flash
        if request.endpoint == 'static' or request.path.startswith('/static/'):
            return
        if current_user.is_authenticated:
            # Bind to User-Agent only: binding to IP logged out mobile users on every
            # network change (and behind a proxy remote_addr is the proxy, not the user).
            user_agent = request.headers.get('User-Agent', 'unknown')
            stored_ua = session.get('session_ua')
            if stored_ua is None:
                session['session_ua'] = user_agent
            elif stored_ua != user_agent:
                logout_user()
                session.clear()
                flash('Session invalidated due to suspicious activity.', 'error')
                return redirect(url_for('auth.login'))

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    return app


# Socket.IO connection room management
@socketio.on('connect')
def handle_connect():
    from flask_login import current_user
    from flask_socketio import join_room
    if current_user.is_authenticated:
        join_room(f"user_{current_user.id}")
        if current_user.email:
            join_room(f"email_{current_user.email.strip().lower()}")
        if current_user.branch_id:
            join_room(f"branch_{current_user.branch_id}")
        if current_user.role:
            join_room(f"role_{current_user.role}")
        print(f"[SocketIO] User {current_user.name} connected and joined rooms.")


@socketio.on('disconnect')
def handle_disconnect():
    from flask_login import current_user
    from flask_socketio import leave_room
    if current_user.is_authenticated:
        leave_room(f"user_{current_user.id}")
        if current_user.email:
            leave_room(f"email_{current_user.email.strip().lower()}")
        if current_user.branch_id:
            leave_room(f"branch_{current_user.branch_id}")
        if current_user.role:
            leave_room(f"role_{current_user.role}")
        print(f"[SocketIO] User {current_user.name} disconnected.")


