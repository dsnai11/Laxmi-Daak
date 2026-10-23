from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import login_required, current_user
from functools import wraps
from flask import abort
from app import db
from app.models.user import User
from app.models.branch import Branch
from app.services.import_service import import_branches_from_excel, import_employees_from_excel, generate_branch_template, generate_employee_template
from io import BytesIO
import os
import tempfile

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superadmin':
            abort(403)
        return f(*args, **kwargs)
    return decorated

def admin_or_admin_dept_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(403)
        if current_user.role != 'superadmin' and not current_user.has_permission('can_dispatch_queries'):
            abort(403)
        return f(*args, **kwargs)
    return decorated

@admin_bp.route('/accounts')
@login_required
@superadmin_required
def accounts():
    from app.models.department import Department
    role_filter = request.args.get('role', '')
    search = request.args.get('search', '').strip()
    branch_id = request.args.get('branch_id', type=int)
    department_id = request.args.get('department_id', type=int)
    page = request.args.get('page', 1, type=int)
    
    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    if branch_id:
        query = query.filter_by(branch_id=branch_id)
    if department_id:
        query = query.filter_by(department_id=department_id)
    if search:
        query = query.filter(
            (User.name.ilike(f'%{search}%')) |
            (User.username.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        )
        
    accounts_paginated = query.order_by(User.name).paginate(page=page, per_page=25, error_out=False)
    branches = Branch.query.order_by(Branch.name).all()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    
    return render_template('admin/accounts.html', accounts=accounts_paginated, branches=branches, departments=departments, role_filter=role_filter, search=search, selected_branch=branch_id, selected_department=department_id)

@admin_bp.route('/branches')
@login_required
@superadmin_required
def redirect_branches():
    return redirect(url_for('admin.accounts', tab='branches'))

@admin_bp.route('/employees')
@login_required
@superadmin_required
def redirect_employees():
    return redirect(url_for('admin.accounts'))

@admin_bp.route('/branches/add', methods=['POST'])
@login_required
@superadmin_required
def add_branch():
    from app.utils import normalize_state_name
    data = request.form
    branch_code = (data.get('branch_code') or '').strip().upper()
    name = (data.get('name') or '').strip()
    city = (data.get('city') or '').strip()
    state = normalize_state_name((data.get('state') or '').strip())
    address = (data.get('address') or '').strip()
    phone = (data.get('phone') or '').strip()
    pincode = (data.get('pincode') or '').strip()
    email = (data.get('email') or '').strip()
    
    if not branch_code or not name:
        return jsonify({'success': False, 'message': 'Branch Code and Branch Name are required'}), 400
        
    # Check if branch code exists
    existing = Branch.query.filter_by(branch_code=branch_code).first()
    if existing:
        return jsonify({'success': False, 'message': f'Branch Code "{branch_code}" already exists'}), 400
        
    branch = Branch(
        branch_code=branch_code,
        name=name,
        city=city,
        state=state,
        address=address,
        phone=phone,
        pincode=pincode,
        email=email,
        is_active=True
    )
    db.session.add(branch)
    db.session.commit()
    
    # Log security audit action
    from app.models.security_log import log_security_action
    log_security_action(
        action='branch_created',
        details=f'Branch created: {branch_code} - {name} ({city}, {state})'
    )
    
    return jsonify({
        'success': True,
        'message': f'Branch "{name}" ({branch_code}) created successfully!'
    })


@admin_bp.route('/branches/edit/<int:branch_id>', methods=['POST'])
@login_required
@superadmin_required
def edit_branch(branch_id):
    from app.utils import normalize_state_name
    branch = db.session.get(Branch, branch_id)
    if not branch:
        return jsonify({'success': False, 'message': 'Branch not found'}), 404
        
    data = request.form
    new_code = (data.get('branch_code') or branch.branch_code or '').strip().upper()
    name = (data.get('name') or branch.name or '').strip()
    city = (data.get('city') or branch.city or '').strip()
    state = normalize_state_name((data.get('state') or branch.state or '').strip())
    address = (data.get('address') or branch.address or '').strip()
    phone = (data.get('phone') or branch.phone or '').strip()
    pincode = (data.get('pincode') or branch.pincode or '').strip()
    email = (data.get('email') or branch.email or '').strip()
    
    if not new_code or not name:
        return jsonify({'success': False, 'message': 'Branch Code and Branch Name are required'}), 400
        
    if new_code != branch.branch_code:
        existing = Branch.query.filter(Branch.branch_code == new_code, Branch.id != branch.id).first()
        if existing:
            return jsonify({'success': False, 'message': f'Branch Code "{new_code}" is already in use by another branch'}), 400
            
    old_details = f'{branch.branch_code} - {branch.name} ({branch.city}, {branch.state})'
    
    branch.branch_code = new_code
    branch.name = name
    branch.city = city
    branch.state = state
    branch.address = address
    branch.phone = phone
    branch.pincode = pincode
    branch.email = email
    
    db.session.commit()
    
    # Log security audit action
    from app.models.security_log import log_security_action
    log_security_action(
        action='branch_edited',
        details=f'Branch edited: {new_code} - {name} ({city}, {state}) | Previous: {old_details}',
        user_id=current_user.id,
        username=current_user.username
    )
    
    return jsonify({
        'success': True,
        'message': f'Branch "{name}" ({new_code}) details updated successfully!'
    })

@admin_bp.route('/branches/delete/<int:branch_id>', methods=['POST'])
@login_required
@superadmin_required
def delete_branch(branch_id):
    branch = db.session.get(Branch, branch_id)
    if not branch:
        return jsonify({'success': False, 'message': 'Branch not found'}), 404
        
    # Check if any users are assigned to this branch
    user_count = User.query.filter_by(branch_id=branch_id).count()
    if user_count > 0:
        return jsonify({'success': False, 'message': f'Cannot delete branch. {user_count} account(s) are assigned to it.'}), 400
        
    name = branch.name
    code = branch.branch_code
    db.session.delete(branch)
    db.session.commit()
    
    # Log security audit action
    from app.models.security_log import log_security_action
    log_security_action(
        action='branch_deleted',
        details=f'Branch deleted: {code} - {name}',
        user_id=current_user.id,
        username=current_user.username
    )
    
    return jsonify({
        'success': True,
        'message': f'Branch "{name}" ({code}) deleted successfully!'
    })

@admin_bp.route('/accounts/template')
@admin_bp.route('/branches/template')
@login_required
@superadmin_required
def accounts_template():
    wb = generate_branch_template()
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='accounts_import_template.xlsx')

@admin_bp.route('/accounts/import', methods=['POST'])
@admin_bp.route('/branches/import', methods=['POST'])
@login_required
@superadmin_required
def import_accounts():
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('admin.accounts'))
        
    file = request.files['file']
    if not file or not file.filename:
        flash('No file selected', 'error')
        return redirect(url_for('admin.accounts'))

    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('Please upload a valid Excel file (.xlsx)', 'error')
        return redirect(url_for('admin.accounts'))
        
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        file.save(tmp.name)
        results = import_branches_from_excel(tmp.name)
    os.unlink(tmp.name)
    
    flash(f"Bulk Import Complete: {results['success']} accounts created/updated, {results['failed']} failed", 'success' if results['failed'] == 0 else 'warning')
    if results.get('errors'):
        for err in results['errors'][:3]:
            flash(err, 'error')
            
    return redirect(url_for('admin.accounts'))

@admin_bp.route('/accounts/add', methods=['POST'])
@login_required
@superadmin_required
def add_account():
    data = request.form
    name = (data.get('name') or '').strip()
    username = (data.get('username') or '').strip().lower()
    password = (data.get('password') or '').strip()
    role = data.get('role', 'employee')
    branch_id = data.get('branch_id', type=int) or None
    email = (data.get('email') or '').strip()
    phone = (data.get('phone') or '').strip()
    
    if not name or not username:
        return jsonify({'success': False, 'message': 'Name and Username (Login ID) are required'}), 400
        
    from sqlalchemy import func
    if User.query.filter(func.lower(User.username) == username.lower()).first():
        return jsonify({'success': False, 'message': f'Username "{username}" already exists'}), 400
        
    # Auto-create branch if role is manager / branch_login and no branch_id selected
    if role in ('manager', 'branch_login') and not branch_id:
        branch_code = username.upper()
        existing_b = Branch.query.filter_by(branch_code=branch_code).first()
        if existing_b:
            branch_id = existing_b.id
        else:
            new_b = Branch(
                branch_code=branch_code,
                name=name,
                city=data.get('city', ''),
                state=data.get('state', ''),
                email=email,
                phone=phone,
                is_active=True
            )
            db.session.add(new_b)
            db.session.flush()
            branch_id = new_b.id
            
    department_id = data.get('department_id', type=int) or None
    department_name = ''
    if department_id:
        from app.models.department import Department
        dept = db.session.get(Department, department_id)
        if dept:
            department_name = dept.name
            
    user = User(
        username=username,
        name=name,
        email=email,
        phone=phone,
        role='manager' if role == 'branch_login' else role,
        branch_id=branch_id,
        department_id=department_id,
        department_name=department_name,
        is_active=True
    )
    generated_password = None
    if not password:
        import secrets
        generated_password = secrets.token_urlsafe(9)
        password = generated_password
    user.set_password(password)
    
    # Parse and set permissions
    valid_keys = [
        'can_scan', 'can_raise_query', 'can_dispatch_queries', 
        'can_new_dispatch', 'can_bulk_dispatch', 'can_view_parcels', 
        'can_overdue', 'can_archive', 'can_billing_rates', 'can_reports'
    ]
    perms_dict = {}
    for key in valid_keys:
        perms_dict[key] = (data.get(key) == 'true' or data.get(key) == 'on')
    user.set_permissions(perms_dict)
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Account "{name}" created successfully! Login ID: {username}'
                   + (f' | Temporary password: {generated_password}' if generated_password else ''),
        'username': username
    })

@admin_bp.route('/accounts/edit/<int:user_id>', methods=['POST'])
@login_required
@superadmin_required
def edit_account(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Account not found'}), 404
        
    data = request.form
    user.name = data.get('name', user.name)
    new_username = (data.get('username') or user.username).strip().lower()
    
    from sqlalchemy import func
    if new_username.lower() != user.username.lower():
        existing = User.query.filter(func.lower(User.username) == new_username.lower(), User.id != user.id).first()
        if existing:
            return jsonify({'success': False, 'message': f'Username "{new_username}" is taken'}), 400
        user.username = new_username
        
    user.email = data.get('email', user.email)
    user.phone = data.get('phone', user.phone)
    user.role = data.get('role', user.role)
    user.branch_id = data.get('branch_id', type=int) or user.branch_id
    
    # Update department details
    dept_id_val = data.get('department_id')
    if dept_id_val is not None:
        if dept_id_val == '':
            user.department_id = None
            user.department_name = ''
        else:
            try:
                dept_id = int(dept_id_val)
                user.department_id = dept_id
                from app.models.department import Department
                dept = db.session.get(Department, dept_id)
                user.department_name = dept.name if dept else ''
            except ValueError:
                pass
    
    # Update associated branch's address if provided
    branch_address = data.get('branch_address')
    if user.branch_id and branch_address is not None:
        from app.models.branch import Branch
        branch = db.session.get(Branch, user.branch_id)
        if branch:
            branch.address = branch_address.strip()
            
    # Parse and set permissions
    valid_keys = [
        'can_scan', 'can_raise_query', 'can_dispatch_queries', 
        'can_new_dispatch', 'can_bulk_dispatch', 'can_view_parcels', 
        'can_overdue', 'can_archive', 'can_billing_rates', 'can_reports'
    ]
    perms_dict = {}
    for key in valid_keys:
        perms_dict[key] = (data.get(key) == 'true' or data.get(key) == 'on')
    user.set_permissions(perms_dict)
            
    db.session.commit()
    return jsonify({'success': True, 'message': f'Account "{user.name}" updated successfully'})

@admin_bp.route('/accounts/credentials/<int:user_id>', methods=['POST'])
@login_required
@superadmin_required
def update_account_credentials(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Account not found'}), 404
        
    username = (request.form.get('username') or '').strip().lower()
    password = (request.form.get('password') or '').strip()
    
    if not username:
        return jsonify({'success': False, 'message': 'Username is required'}), 400
        
    existing = User.query.filter(User.username == username, User.id != user.id).first()
    if existing:
        return jsonify({'success': False, 'message': f'Username "{username}" is taken'}), 400
        
    user.username = username
    if password:
        user.set_password(password)
        
    db.session.commit()
    return jsonify({'success': True, 'message': f'Credentials updated for {user.name}! Login ID: {username}'})

@admin_bp.route('/accounts/delete/<int:user_id>', methods=['POST'])
@login_required
@superadmin_required
def delete_account(user_id):
    if current_user.id == user_id:
        return jsonify({'success': False, 'message': 'You cannot delete your own logged-in admin account'}), 400
        
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'Account not found'}), 404
        
    name = user.name or user.username
    
    from app.models.parcel import Parcel
    from app.models.scan_log import ScanLog
    
    parcels = Parcel.query.filter_by(created_by=user_id).all()
    for p in parcels:
        p.created_by = None
        
    scan_logs = ScanLog.query.filter_by(employee_id=user_id).all()
    for sl in scan_logs:
        sl.employee_id = None
        
    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Account "{name}" deleted successfully'})

# ─────────────────────────────────────────
# Master Item List Management
# ─────────────────────────────────────────

@admin_bp.route('/items')
@login_required
@superadmin_required
def items():
    from app.models.item import Item
    page = request.args.get('page', 1, type=int)
    items_paginated = Item.query.order_by(Item.name).paginate(page=page, per_page=20)
    return render_template('admin/items.html', items=items_paginated)

@admin_bp.route('/items/add', methods=['POST'])
@login_required
@superadmin_required
def add_item():
    from app.models.item import Item
    name = request.form.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Item name is required'})
    
    existing = Item.query.filter(Item.name.ilike(name)).first()
    if existing:
        return jsonify({'success': False, 'message': f'Item "{name}" already exists'})
    
    new_item = Item(name=name)
    db.session.add(new_item)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Item "{name}" added to master list'})

@admin_bp.route('/items/delete/<int:item_id>', methods=['POST'])
@login_required
@superadmin_required
def delete_item(item_id):
    from app.models.item import Item
    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({'success': False, 'message': 'Item not found'}), 404
    
    name = item.name
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Item "{name}" deleted from master list'})

@admin_bp.route('/billing', methods=['GET', 'POST'])
@login_required
@superadmin_required
def billing_settings():
    from app.models.state_billing_rate import StateBillingRate
    from app.utils import normalize_state_name
    
    state = normalize_state_name(request.args.get('state', 'Default'))
    if not state:
        state = 'Default'
        
    if request.method == 'POST':
        if current_user.role != 'superadmin':
            flash('Only superadmins can update billing configurations.', 'error')
            return redirect(url_for('admin.billing_settings', state=state))
            
        post_state = normalize_state_name(request.form.get('state', 'Default'))
        if not post_state:
            post_state = 'Default'
            
        try:
            rates = StateBillingRate.query.filter_by(state=post_state).all()
            for rate in rates:
                base_val = request.form.get(f'base_rate_{rate.id}')
                per_kg_val = request.form.get(f'per_kg_rate_{rate.id}')
                if base_val is not None:
                    rate.base_rate = float(base_val)
                if per_kg_val is not None:
                    rate.per_kg_rate = float(per_kg_val)
                # Save Pushpak-specific gram-based rates
                if rate.courier_name == 'Pushpak':
                    pn_base  = request.form.get(f'pushpak_normal_base_{rate.id}')
                    pn_extra = request.form.get(f'pushpak_normal_extra_{rate.id}')
                    pp_base  = request.form.get(f'pushpak_premium_base_{rate.id}')
                    pp_extra = request.form.get(f'pushpak_premium_extra_{rate.id}')
                    if pn_base  is not None: rate.pushpak_normal_base  = float(pn_base)
                    if pn_extra is not None: rate.pushpak_normal_extra = float(pn_extra)
                    if pp_base  is not None: rate.pushpak_premium_base  = float(pp_base)
                    if pp_extra is not None: rate.pushpak_premium_extra = float(pp_extra)

                    
            db.session.commit()
            
            # Audit log
            from app.models.security_log import log_security_action
            log_security_action(
                action='billing_rates_updated',
                details=f'Superadmin updated billing rates for state: {post_state}'
            )
            
            flash(f'Billing rates for state "{post_state}" updated successfully!', 'success')
            return redirect(url_for('admin.billing_settings', state=post_state))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating billing rates: {str(e)}', 'error')
            
    # GET Request: Fetch distinct states from registered branches & state billing rates
    branch_states = [s[0] for s in db.session.query(Branch.state).filter(Branch.state != '', Branch.state != None).distinct().all()]
    rate_states = [r[0] for r in db.session.query(StateBillingRate.state).filter(StateBillingRate.state != '', StateBillingRate.state != None).distinct().all()]
    
    # Normalize list of states to ensure uniqueness and proper naming
    normalized_states = set()
    for s in (branch_states + rate_states):
        normalized_states.add(normalize_state_name(s))
        
    states_list = sorted(list(normalized_states))
    
    if 'Default' not in states_list:
        states_list.insert(0, 'Default')
    else:
        # Move Default to the first position
        states_list.remove('Default')
        states_list.insert(0, 'Default')
        
    # Get rates for selected state
    rates = StateBillingRate.query.filter_by(state=state).all()
    if not rates:
        # Auto-clone Default rates if they don't exist yet for this state
        default_rates = StateBillingRate.query.filter_by(state='Default').all()
        if not default_rates:
            # Seed default rates if empty (safety net)
            from app.models.billing_rate import BillingRate
            old_rates = BillingRate.query.all()
            for old in old_rates:
                db.session.add(StateBillingRate(
                    state='Default',
                    courier_name=old.name,
                    base_rate=old.base_rate,
                    per_kg_rate=old.per_kg_rate
                ))
            db.session.commit()
            default_rates = StateBillingRate.query.filter_by(state='Default').all()
            
        for dr in default_rates:
            db.session.add(StateBillingRate(
                state=state,
                courier_name=dr.courier_name,
                base_rate=dr.base_rate,
                per_kg_rate=dr.per_kg_rate
            ))
        db.session.commit()
        rates = StateBillingRate.query.filter_by(state=state).all()
        
    # Fetch Blue Dart Rajasthan rate to always show both rates clearly
    bluedart_rj = StateBillingRate.query.filter_by(state='Rajasthan', courier_name='Blue Dart').first()
    bluedart_rj_rate = bluedart_rj.base_rate if bluedart_rj else 350.0
    bluedart_default = StateBillingRate.query.filter_by(state='Default', courier_name='Blue Dart').first()
    bluedart_default_rate = bluedart_default.base_rate if bluedart_default else 550.0

    return render_template('admin/billing.html', rates=rates, states=states_list, selected_state=state,
                           bluedart_rj_rate=bluedart_rj_rate, bluedart_default_rate=bluedart_default_rate)


@admin_bp.route('/billing/add-state', methods=['POST'])
@login_required
@superadmin_required
def add_billing_state():
    from app.models.state_billing_rate import StateBillingRate
    from app.utils import normalize_state_name
    
    raw_state_name = request.form.get('state_name', '').strip()
    if not raw_state_name:
        flash('State name is required.', 'error')
        return redirect(url_for('admin.billing_settings'))
        
    state_name = normalize_state_name(raw_state_name)
    
    # Check if rates already exist for this state
    exists = StateBillingRate.query.filter_by(state=state_name).first()
    if not exists:
        # Clone Default rates
        default_rates = StateBillingRate.query.filter_by(state='Default').all()
        if not default_rates:
            # Safety fallback seeds if Default is empty
            from app.models.billing_rate import BillingRate
            old_rates = BillingRate.query.all()
            for old in old_rates:
                db.session.add(StateBillingRate(
                    state='Default',
                    courier_name=old.name,
                    base_rate=old.base_rate,
                    per_kg_rate=old.per_kg_rate
                ))
            db.session.commit()
            default_rates = StateBillingRate.query.filter_by(state='Default').all()
            
        for dr in default_rates:
            db.session.add(StateBillingRate(
                state=state_name,
                courier_name=dr.courier_name,
                base_rate=dr.base_rate,
                per_kg_rate=dr.per_kg_rate
            ))
        db.session.commit()
        
        # Log security action
        from app.models.security_log import log_security_action
        log_security_action(
            action='billing_state_added',
            details=f'Superadmin added new billing state: {state_name}'
        )
        
        flash(f'State "{state_name}" added successfully and initialized with default rates!', 'success')
    else:
        flash(f'State "{state_name}" already exists.', 'info')
        
    return redirect(url_for('admin.billing_settings', state=state_name))

@admin_bp.route('/billing/delete/<state_name>', methods=['POST'])
@login_required
@superadmin_required
def delete_billing_state(state_name):
    from app.models.state_billing_rate import StateBillingRate
    from app.utils import normalize_state_name
    
    normalized = normalize_state_name(state_name)
    if normalized == 'Default':
        flash('Default billing rates cannot be deleted.', 'error')
        return redirect(url_for('admin.billing_settings'))
        
    # Delete all rates matching this state
    deleted_count = StateBillingRate.query.filter_by(state=normalized).delete()
    db.session.commit()
    
    # Log security action
    from app.models.security_log import log_security_action
    log_security_action(
        action='billing_state_deleted',
        details=f'Superadmin deleted billing rates for state: {normalized} (removed {deleted_count} records)'
    )
    
    flash(f'State "{normalized}" and its billing configurations deleted successfully!', 'success')
    return redirect(url_for('admin.billing_settings', state='Default'))

@admin_bp.route('/departments', methods=['GET'])
@login_required
@superadmin_required
def departments():
    from app.models.department import Department
    from app.models.user import User
    
    depts = Department.query.order_by(Department.name).all()
    
    total_depts = len(depts)
    depts_with_staff = 0
    for d in depts:
        staff_count = User.query.filter_by(department_id=d.id, is_active=True).count()
        d.temp_staff_count = staff_count
        if staff_count > 0:
            depts_with_staff += 1
            
    return render_template('admin/departments.html', depts=depts, total_depts=total_depts, depts_with_staff=depts_with_staff)

@admin_bp.route('/departments/add', methods=['POST'])
@login_required
@superadmin_required
def add_department():
    from app.models.department import Department
    name = request.form.get('name', '').strip()
    if not name:
        flash('Department name is required.', 'error')
        return redirect(url_for('admin.departments'))
        
    # Check if duplicate
    existing = Department.query.filter_by(name=name).first()
    if existing:
        flash('Department with this name already exists.', 'error')
        return redirect(url_for('admin.departments'))
        
    try:
        # Generate a unique code — if first 3 letters clash, try appending digits
        base_code = name[:3].upper()
        code = base_code
        suffix = 1
        while Department.query.filter_by(code=code).first():
            code = base_code[:2] + str(suffix)
            suffix += 1
        new_dept = Department(name=name, code=code)
        db.session.add(new_dept)
        db.session.commit()
        flash(f'Department "{name}" added successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding department: {str(e)}', 'error')
        
    return redirect(url_for('admin.departments'))

@admin_bp.route('/departments/delete/<int:dept_id>', methods=['POST'])
@login_required
@superadmin_required
def delete_department(dept_id):
    from app.models.department import Department
    from app.models.user import User
    
    dept = db.session.get(Department, dept_id)
    if not dept:
        flash('Department not found.', 'error')
        return redirect(url_for('admin.departments'))
        
    # Check if has staff
    staff_count = User.query.filter_by(department_id=dept.id, is_active=True).count()
    if staff_count > 0:
        flash('Cannot delete department because it still has active staff members assigned.', 'error')
        return redirect(url_for('admin.departments'))
        
    try:
        name = dept.name
        db.session.delete(dept)
        db.session.commit()
        flash(f'Department "{name}" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting department: {str(e)}', 'error')
        
    return redirect(url_for('admin.departments'))


# ─────────────────────────────────────────────────────────────────────────────
#  DISPATCH QUERY MANAGEMENT  (Admin side of the workflow)
# ─────────────────────────────────────────────────────────────────────────────

@admin_bp.route('/dispatch-queries')
@login_required
@admin_or_admin_dept_required
def dispatch_queries():
    """Admin dashboard — all department dispatch queries."""
    from app.models.parcel import Parcel
    from app.models.branch import Branch
    from app.models.department import Department

    page         = request.args.get('page', 1, type=int)
    status       = request.args.get('status', '')
    dept_filter  = request.args.get('department_id', '', type=str)

    query = Parcel.query.filter(Parcel.status.in_(
        ['query_raised', 'picked_up', 'in_transit', 'delivered_pending', 'closed', 'failed']
    ))

    if status:
        query = query.filter_by(status=status)

    if dept_filter:
        try:
            query = query.filter(
                (Parcel.sender_department_id == int(dept_filter)) |
                (Parcel.receiver_department_id == int(dept_filter))
            )
        except ValueError:
            pass

    parcels      = query.order_by(Parcel.dispatched_at.desc()).paginate(page=page, per_page=25, error_out=False)
    departments  = Department.query.filter_by(is_active=True).order_by(Department.name).all()

    # Counts for stat cards
    pending_pickup_count    = Parcel.query.filter_by(status='query_raised').count()
    in_transit_count        = Parcel.query.filter(Parcel.status.in_(['picked_up', 'in_transit'])).count()
    pending_confirm_count   = Parcel.query.filter_by(status='delivered_pending').count()
    closed_count            = Parcel.query.filter_by(status='closed').count()

    return render_template('admin/dispatch_queries.html',
                           parcels=parcels, status=status,
                           departments=departments, selected_dept=dept_filter,
                           pending_pickup_count=pending_pickup_count,
                           in_transit_count=in_transit_count,
                           pending_confirm_count=pending_confirm_count,
                           closed_count=closed_count)


@admin_bp.route('/dispatch-query/pickup/<int:parcel_id>', methods=['GET', 'POST'])
@login_required
@admin_or_admin_dept_required
def pickup_dispatch_query(parcel_id):
    """Admin picks up the physical parcel from the department and dispatches it."""
    from app.models.parcel import Parcel
    from app.models.scan_log import ScanLog
    from app.models.branch import Branch
    from datetime import datetime

    parcel = db.session.get(Parcel, parcel_id)
    if not parcel:
        flash('Query not found.', 'error')
        return redirect(url_for('admin.dispatch_queries'))

    if parcel.status != 'query_raised':
        flash('This query has already been picked up or is in a later stage.', 'warning')
        return redirect(url_for('admin.dispatch_queries'))

    if request.method == 'POST':
        try:
            raw_w = float(request.form.get('weight', 0) or 0)
            weight_unit = request.form.get('weight_unit', 'kg').lower()
            parcel.weight = raw_w / 1000.0 if weight_unit == 'gms' else raw_w
            parcel.billing_amount = float(request.form.get('billing_amount', 0) or 0)

            if transfer_mode == 'by_courier':
                cp = request.form.get('courier_partner', '')
                if cp == 'Other Company':
                    cp = request.form.get('other_courier_name', '').strip()
                parcel.courier_partner = cp
                parcel.courier_id      = request.form.get('courier_id', '')
            elif transfer_mode == 'by_bus':
                parcel.bus_number   = request.form.get('bus_number', '')
                parcel.driver_phone = request.form.get('driver_phone', '')
            elif transfer_mode == 'by_hand':
                parcel.hand_carry_name  = request.form.get('hand_carry_name', '')
                parcel.hand_carry_phone = request.form.get('hand_carry_phone', '')

            parcel.special_instructions = request.form.get('special_instructions', parcel.special_instructions)
            parcel.status = 'picked_up'

            branch = db.session.get(Branch, current_user.branch_id) if current_user.branch_id else None
            scan_log = ScanLog(
                parcel_id=parcel.id,
                tracking_number=parcel.tracking_number,
                branch_id=current_user.branch_id,
                branch_name=branch.name if branch else 'Admin Office',
                employee_id=current_user.id,
                employee_name=current_user.name,
                action='picked_up',
                notes=f'Courier collected by Admin team ({current_user.name}) and dispatched via {parcel.transfer_mode_label}'
            )
            db.session.add(scan_log)
            db.session.commit()

            # --- Send email notifications ---
            try:
                from app.services.email_service import send_dispatch_receiver_notification, send_dispatch_sender_confirmation
                from app.models.user import User
                
                # Fetch branch names
                sender_b_name = parcel.sender_branch.name if parcel.sender_branch else 'Source Branch'
                receiver_b_name = parcel.receiver_branch.name if parcel.receiver_branch else (parcel.receiver_branch_name or 'Destination Branch')

                # Gather receiver emails (ONLY recipient email or recipient branch email if no recipient email specified)
                receiver_emails = set()
                if parcel.receiver_email and '@' in parcel.receiver_email:
                    receiver_emails.add(parcel.receiver_email.strip())
                elif parcel.receiver_branch and parcel.receiver_branch.email and '@' in parcel.receiver_branch.email:
                    receiver_emails.add(parcel.receiver_branch.email.strip())

                # Gather sender emails (ONLY sender email or sender branch email)
                sender_emails = set()
                if parcel.sender_email and '@' in parcel.sender_email:
                    sender_emails.add(parcel.sender_email.strip())
                if parcel.sender_branch and parcel.sender_branch.email and '@' in parcel.sender_branch.email:
                    sender_emails.add(parcel.sender_branch.email.strip())

                # Send receiver notifications
                for r_email in receiver_emails:
                    send_dispatch_receiver_notification(
                        receiver_email=r_email,
                        receiver_name=parcel.receiver_name,
                        tracking_number=parcel.tracking_number,
                        sender_name=parcel.sender_name,
                        sender_branch=sender_b_name,
                        receiver_branch=receiver_b_name,
                        transfer_mode=parcel.transfer_mode_label,
                        courier_partner=parcel.courier_partner,
                        courier_id=parcel.courier_id,
                        company_name=current_app.config['COMPANY_NAME'],
                        base_url=current_app.config['BASE_URL']
                    )

                # Send sender confirmations
                for s_email in sender_emails:
                    send_dispatch_sender_confirmation(
                        sender_email=s_email,
                        sender_name=parcel.sender_name,
                        tracking_number=parcel.tracking_number,
                        receiver_name=parcel.receiver_name,
                        receiver_branch=receiver_b_name,
                        transfer_mode=parcel.transfer_mode_label,
                        courier_partner=parcel.courier_partner,
                        courier_id=parcel.courier_id,
                        company_name=current_app.config['COMPANY_NAME'],
                        base_url=current_app.config['BASE_URL']
                    )
            except Exception as e:
                print(f"Error sending dispatch notification emails during query pickup: {e}")

            flash(f'Query {parcel.tracking_number} picked up and dispatched successfully!', 'success')
            return redirect(url_for('admin.dispatch_queries'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error processing pickup: {str(e)}', 'error')

    return render_template('admin/pickup_dispatch.html', parcel=parcel)


@admin_bp.route('/dispatch-query/mark-delivered/<int:parcel_id>', methods=['POST'])
@login_required
@admin_or_admin_dept_required
def mark_query_delivered(parcel_id):
    """Admin marks the courier as received by the receiver — awaiting sender's confirmation."""
    from app.models.parcel import Parcel
    from app.models.scan_log import ScanLog
    from app.models.branch import Branch

    parcel = db.session.get(Parcel, parcel_id)
    if not parcel:
        flash('Query not found.', 'error')
        return redirect(url_for('admin.dispatch_queries'))

    if parcel.status not in ['picked_up', 'in_transit']:
        flash('This query must be in "Picked Up" or "In Transit" state to mark it as delivered.', 'warning')
        return redirect(url_for('admin.dispatch_queries'))

    try:
        parcel.status = 'delivered_pending'
        branch = db.session.get(Branch, current_user.branch_id) if current_user.branch_id else None
        scan_log = ScanLog(
            parcel_id=parcel.id,
            tracking_number=parcel.tracking_number,
            branch_id=current_user.branch_id,
            branch_name=branch.name if branch else 'Admin Office',
            employee_id=current_user.id,
            employee_name=current_user.name,
            action='delivered_pending',
            notes=f'Receiver confirmed receipt. Awaiting sender confirmation. (Updated by {current_user.name})'
        )
        db.session.add(scan_log)
        db.session.commit()

        # Notify the sender that the parcel is delivered and needs their confirmation
        try:
            from app.services.email_service import send_query_delivered_pending_notification
            send_query_delivered_pending_notification(
                sender_email=parcel.sender_email,
                sender_name=parcel.sender_name,
                tracking_number=parcel.tracking_number,
                receiver_name=parcel.receiver_name,
                company_name=current_app.config['COMPANY_NAME'],
                base_url=current_app.config['BASE_URL']
            )
        except Exception as e:
            print(f"Error sending query delivered confirmation email: {e}")

        flash(f'Query {parcel.tracking_number} marked as delivered. Waiting for sender confirmation.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error marking delivered: {str(e)}', 'error')

    return redirect(url_for('admin.dispatch_queries'))


@admin_bp.route('/security-logs')
@login_required
@superadmin_required
def security_logs():
    """Superadmin: view all security audit logs."""
    from app.models.security_log import SecurityLog
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    action_filter = request.args.get('action', '').strip()
    
    query = SecurityLog.query
    
    if action_filter:
        query = query.filter_by(action=action_filter)
        
    if search:
        query = query.filter(
            (SecurityLog.username.ilike(f'%{search}%')) |
            (SecurityLog.details.ilike(f'%{search}%')) |
            (SecurityLog.ip_address.ilike(f'%{search}%'))
        )
        
    logs = query.order_by(SecurityLog.timestamp.desc()).paginate(page=page, per_page=30, error_out=False)
    
    # Get distinct action types for filter dropdown
    distinct_actions = [r[0] for r in db.session.query(SecurityLog.action).distinct().all()]
    
    return render_template('admin/security_logs.html', logs=logs, search=search, selected_action=action_filter, distinct_actions=distinct_actions)


@admin_bp.route('/query/<int:parcel_id>/close', methods=['POST'])
@login_required
@admin_or_admin_dept_required
def close_query(parcel_id):
    """Sender (admin/manager) confirms delivery and closes the query."""
    from app.models.parcel import Parcel
    from app.models.scan_log import ScanLog
    from app.models.branch import Branch
    from datetime import datetime

    parcel = db.session.get(Parcel, parcel_id)
    if not parcel:
        flash('Query not found.', 'error')
        return redirect(url_for('admin.dispatch_queries'))

    if parcel.status != 'delivered_pending':
        flash('Only parcels awaiting sender confirmation can be closed.', 'warning')
        return redirect(url_for('admin.dispatch_queries'))

    try:
        parcel.status = 'closed'
        branch = db.session.get(Branch, current_user.branch_id) if current_user.branch_id else None
        scan_log = ScanLog(
            parcel_id=parcel.id,
            tracking_number=parcel.tracking_number,
            branch_id=current_user.branch_id,
            branch_name=branch.name if branch else 'Admin Office',
            employee_id=current_user.id,
            employee_name=current_user.name,
            action='closed',
            notes=f'Sender confirmed delivery and closed the query. (Confirmed by {current_user.name})'
        )
        db.session.add(scan_log)
        db.session.commit()

        from app.models.security_log import log_security_action
        log_security_action('query_closed_by_sender', f"Sender closed query {parcel.tracking_number}.", user_id=current_user.id, username=current_user.username)

        flash(f'Query {parcel.tracking_number} successfully confirmed and closed. ✅', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error closing query: {str(e)}', 'error')

    return redirect(url_for('admin.dispatch_queries'))

