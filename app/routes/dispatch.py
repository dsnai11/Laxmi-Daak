from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, abort
from flask_login import login_required, current_user
from app import db
from app.models.branch import Branch
from app.models.department import Department
from app.models.parcel import Parcel, generate_tracking_number, get_user_parcel_filter
from app.models.scan_log import ScanLog
from app.models.user import User
from app.services.qr_service import generate_qr_code
from app.services.email_service import send_dispatch_notification, send_dispatch_receiver_notification, send_dispatch_sender_confirmation, send_parcel_cancellation_notification
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from functools import wraps

dispatch_bp = Blueprint('dispatch', __name__, url_prefix='/dispatch')

def permission_required(key):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated or not current_user.has_permission(key):
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@dispatch_bp.route('/new', methods=['GET', 'POST'])
@login_required
@permission_required('can_new_dispatch')
def new_dispatch():
    from app.models.item import Item
    branches = Branch.query.filter_by(is_active=True).order_by(Branch.name).all()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    users = User.query.filter(User.is_active == True).order_by(User.name).all()
    items = Item.query.order_by(Item.name).all()
    
    if request.method == 'POST':
        try:
            tracking_number = generate_tracking_number()
            # Ensure unique
            while Parcel.query.filter_by(tracking_number=tracking_number).first():
                tracking_number = generate_tracking_number()
            
            # Handle photo uploads
            photos = []
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], tracking_number)
            os.makedirs(upload_dir, exist_ok=True)
            
            for photo_file in request.files.getlist('photos'):
                if photo_file and photo_file.filename and allowed_file(photo_file.filename):
                    fname = secure_filename(photo_file.filename)
                    save_path = os.path.join(upload_dir, fname)
                    photo_file.save(save_path)
                    photos.append(f'/static/uploads/{tracking_number}/{fname}')
            
            # Generate QR code
            qr_result = generate_qr_code(tracking_number, current_app.config['BASE_URL'])
            
            # Get branch & department details
            sender_branch_id = request.form.get('sender_branch_id')
            receiver_branch_id = request.form.get('receiver_branch_id')
            
            sender_branch = db.session.get(Branch, int(sender_branch_id)) if sender_branch_id else None
            if not sender_branch_id and current_user.branch_id:
                sender_branch_id = current_user.branch_id
                sender_branch = db.session.get(Branch, current_user.branch_id)
                
            sender_department_id = request.form.get('sender_department_id')
            receiver_department_id = request.form.get('receiver_department_id')
            
            sender_department = db.session.get(Department, int(sender_department_id)) if (sender_department_id and sender_department_id != '') else None
            if not sender_department_id and current_user.department_id:
                sender_department_id = current_user.department_id
                sender_department = db.session.get(Department, current_user.department_id)
                
            receiver_department = db.session.get(Department, int(receiver_department_id)) if (receiver_department_id and receiver_department_id != '') else None
            
            # Parse optional due date
            due_date_str = request.form.get('due_date', '')
            due_date = None
            if due_date_str:
                try:
                    from datetime import date
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            
            receiver_email = request.form.get('receiver_email', '')
            parcel = Parcel(
                tracking_number=tracking_number,
                qr_code_path=qr_result['qr_path'],
                sender_name=request.form.get('sender_name', ''),
                sender_phone=request.form.get('sender_phone', ''),
                sender_email=request.form.get('sender_email', ''),
                sender_address=request.form.get('sender_address', ''),
                sender_branch_id=int(sender_branch_id) if sender_branch_id else None,
                sender_department_id=int(sender_department_id) if sender_department_id else None,
                sender_department_name=sender_department.name if sender_department else '',
                receiver_name=request.form.get('receiver_name', ''),
                receiver_phone=request.form.get('receiver_phone', ''),
                receiver_email=receiver_email,
                receiver_address=request.form.get('receiver_address', ''),
                receiver_branch_id=int(receiver_branch_id) if receiver_branch_id else None,
                receiver_department_id=int(receiver_department_id) if receiver_department_id else None,
                receiver_department_name=receiver_department.name if receiver_department else '',
                description=request.form.get('description', ''),
                priority=request.form.get('priority', 'normal').lower(),
                weight=(float(request.form.get('weight', 0) or 0) / 1000.0 if request.form.get('weight_unit', 'kg').lower() == 'gms' else float(request.form.get('weight', 0) or 0)),
                transfer_mode=request.form.get('transfer_mode', 'by_courier'),
                courier_partner=(request.form.get('other_courier_name', '').strip() if request.form.get('courier_partner') == 'Other Company' else request.form.get('courier_partner', '')) if request.form.get('transfer_mode') == 'by_courier' else '',
                courier_id=request.form.get('courier_id', '') if request.form.get('transfer_mode') == 'by_courier' else '',
                bus_number=request.form.get('bus_number', '') if request.form.get('transfer_mode') == 'by_bus' else '',
                driver_phone=request.form.get('driver_phone', '') if request.form.get('transfer_mode') == 'by_bus' else '',
                hand_carry_name=request.form.get('hand_carry_name', '') if request.form.get('transfer_mode') == 'by_hand' else '',
                hand_carry_phone=request.form.get('hand_carry_phone', '') if request.form.get('transfer_mode') == 'by_hand' else '',
                billing_amount=float(request.form.get('billing_amount', 0) or 0),
                special_instructions=request.form.get('special_instructions', ''),
                status='pending',
                current_branch_id=int(sender_branch_id) if sender_branch_id else None,
                created_by=current_user.id,
                dispatched_at=datetime.utcnow(),
                due_date=due_date
            )
            parcel.photos = photos
            db.session.add(parcel)
            db.session.flush()
            
            # Create initial scan log
            scan_log = ScanLog(
                parcel_id=parcel.id,
                tracking_number=tracking_number,
                branch_id=sender_branch.id if sender_branch else None,
                branch_name=sender_branch.name if sender_branch else current_user.branch_name,
                employee_id=current_user.id,
                employee_name=current_user.name,
                action='dispatched',
                notes='File dispatched'
            )
            db.session.add(scan_log)
            db.session.commit()
            
            # Log security action
            from app.models.security_log import log_security_action
            log_security_action('dispatch_created', f"Created new dispatch {tracking_number} to {parcel.receiver_name} ({parcel.receiver_branch_name or 'custom destination'}).", user_id=current_user.id, username=current_user.username)
            
            # Send email notifications to both Receiver & Sender
            sender_b_name = sender_branch.name if sender_branch else (current_user.branch_name or 'Main Office')
            receiver_b_obj = Branch.query.get(int(receiver_branch_id)) if receiver_branch_id else None
            receiver_b_name = receiver_b_obj.name if receiver_b_obj else 'Destination Office'
            
            # Collect ONLY the specific Receiver email (or destination branch email if no receiver email provided)
            receiver_emails = set()
            r_field = request.form.get('receiver_email', '').strip()
            if r_field and '@' in r_field:
                receiver_emails.add(r_field)
            elif receiver_b_obj and receiver_b_obj.email and '@' in receiver_b_obj.email:
                receiver_emails.add(receiver_b_obj.email.strip())

            # Collect ONLY the specific Sender / Source Branch emails
            sender_emails = set()
            s_field = request.form.get('sender_email', '').strip()
            if s_field and '@' in s_field:
                sender_emails.add(s_field)
            # NOTE: current_user.email removed — admin/operator ke email par notification nahi jayegi
            # Sender branch email add karein (branch login ka email)
            if sender_branch and sender_branch.email and '@' in sender_branch.email:
                sender_emails.add(sender_branch.email.strip())

            # 1. Send Receiver Notification to ALL receiver emails (Destination Branch + Receiver)
            for r_email in receiver_emails:
                try:
                    send_dispatch_receiver_notification(
                        receiver_email=r_email,
                        receiver_name=request.form.get('receiver_name', ''),
                        tracking_number=tracking_number,
                        sender_name=request.form.get('sender_name', ''),
                        sender_branch=sender_b_name,
                        receiver_branch=receiver_b_name,
                        transfer_mode=parcel.transfer_mode_label,
                        courier_partner=parcel.courier_partner,
                        company_name=current_app.config['COMPANY_NAME'],
                        base_url=current_app.config['BASE_URL'],
                        courier_id=parcel.courier_id
                    )
                except Exception as e:
                    print(f"Receiver notification email error for {r_email}: {e}")

            # NOTE: Sender confirmation email on dispatch removed as requested.
            # (Sender gets notified only if overdue or when delivered by receiver)

            flash(f'File dispatched successfully! Tracking: {tracking_number}', 'success')

            return redirect(url_for('dispatch.dispatch_success', tracking_number=tracking_number))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error dispatching file: {str(e)}', 'error')
            
    return render_template('dispatch/new.html', branches=branches, users=users, items=items, departments=departments)

@dispatch_bp.route('/success/<tracking_number>')
@login_required
def dispatch_success(tracking_number):
    parcel = Parcel.query.filter_by(tracking_number=tracking_number).first_or_404()
    return render_template('dispatch/success.html', parcel=parcel, tracking_number=tracking_number)

@dispatch_bp.route('/print-label/<tracking_no>')
@login_required
def print_label(tracking_no):
    parcel = Parcel.query.filter_by(tracking_number=tracking_no).first_or_404()
    return render_template('dispatch/print_label.html', parcel=parcel)

@dispatch_bp.route('/list')
@login_required
@permission_required('can_view_parcels')
def dispatch_list():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    search = request.args.get('search', '').strip()
    branch_filter = request.args.get('branch', '')
    dept_filter = request.args.get('department', '')
    filter_type = request.args.get('filter', '').strip()
    
    query = Parcel.query.filter(
        (Parcel.is_archived == False) | (Parcel.is_archived == None)
    )
    
    # Filter for personal scans or deliveries today
    REAL_SCAN_ACTIONS = ('received', 'out_for_delivery', 'delivered', 'failed',
                         'returned', 'qr_scanned', 'picked_up', 'delivered_pending', 'closed')
    if filter_type == 'my_scans_today':
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        from app.models.scan_log import ScanLog
        scanned_ids = [s.parcel_id for s in ScanLog.query.filter(
            ScanLog.employee_id == current_user.id,
            ScanLog.action.in_(REAL_SCAN_ACTIONS),
            ScanLog.timestamp >= today_start
        ).all()]
        query = query.filter(Parcel.id.in_(scanned_ids if scanned_ids else [-1]))
    elif filter_type == 'my_deliveries_today':
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        from app.models.scan_log import ScanLog
        deliv_ids = [s.parcel_id for s in ScanLog.query.filter(
            ScanLog.employee_id == current_user.id,
            ScanLog.action == 'delivered',
            ScanLog.timestamp >= today_start
        ).all()]
        query = query.filter(Parcel.id.in_(deliv_ids if deliv_ids else [-1]))

    # Always apply user-scope filter for non-superadmin to prevent data leakage
    if current_user.role not in ['superadmin']:
        if not filter_type:
            user_cond = get_user_parcel_filter(current_user)
            if user_cond is not None:
                query = query.filter(user_cond)

    else:
        # Branch filter for superadmin
        if branch_filter:
            try:
                query = query.filter(
                    (Parcel.sender_branch_id == int(branch_filter)) |
                    (Parcel.current_branch_id == int(branch_filter))
                )
            except ValueError:
                pass
                
    # Department filter
    if dept_filter:
        try:
            query = query.filter(
                (Parcel.sender_department_id == int(dept_filter)) |
                (Parcel.receiver_department_id == int(dept_filter))
            )
        except ValueError:
            pass
    
    if status:
        query = query.filter_by(status=status)
    
    if search:
        query = query.filter(
            (Parcel.tracking_number.ilike(f'%{search}%')) |
            (Parcel.sender_name.ilike(f'%{search}%')) |
            (Parcel.receiver_name.ilike(f'%{search}%')) |
            (Parcel.sender_phone.ilike(f'%{search}%')) |
            (Parcel.receiver_phone.ilike(f'%{search}%'))
        )
    
    parcels = query.order_by(Parcel.dispatched_at.desc()).paginate(page=page, per_page=25, error_out=False)
    
    branches = []
    if current_user.role == 'superadmin':
        branches = Branch.query.filter_by(is_active=True).order_by(Branch.name).all()
        
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    
    # Overdue count for sidebar badge — user-scoped (same logic as context processor)
    from datetime import date
    from sqlalchemy import or_
    overdue_base = Parcel.query.filter(
        Parcel.due_date != None,
        Parcel.due_date < date.today(),
        Parcel.status.in_(['pending', 'in_transit'])
    ).filter((Parcel.is_archived == False) | (Parcel.is_archived == None))

    if current_user.role == 'superadmin':
        pass  # sees all
    elif current_user.role == 'manager' and current_user.branch_id:
        overdue_base = overdue_base.filter(or_(
            Parcel.sender_branch_id == current_user.branch_id,
            Parcel.current_branch_id == current_user.branch_id,
            Parcel.receiver_branch_id == current_user.branch_id
        ))
    else:
        # Employee: strict personal match only
        strict_conds = [Parcel.created_by == current_user.id]
        if current_user.email and '@' in current_user.email and len(current_user.email.strip()) > 4:
            em = current_user.email.strip()
            strict_conds.append(Parcel.receiver_email.ilike(em))
            strict_conds.append(Parcel.sender_email.ilike(em))
        if current_user.name and len(current_user.name.strip()) > 2:
            nm = current_user.name.strip()
            strict_conds.append(Parcel.receiver_name.ilike(nm))
            strict_conds.append(Parcel.sender_name.ilike(nm))
        overdue_base = overdue_base.filter(or_(*strict_conds))

    overdue_count = overdue_base.count()

    return render_template('dispatch/list.html', parcels=parcels, status=status, search=search, branches=branches, departments=departments, overdue_count=overdue_count, selected_dept=dept_filter)

@dispatch_bp.route('/detail/<tracking_number>')
@login_required
def dispatch_detail(tracking_number):
    parcel = Parcel.query.filter_by(tracking_number=tracking_number).first_or_404()
    scan_history = ScanLog.query.filter_by(parcel_id=parcel.id).order_by(ScanLog.timestamp.asc()).all()
    
    # Filter scans: if user is not superadmin, only show scans up to the first 'delivered' scan
    if not (current_user.is_authenticated and current_user.role == 'superadmin'):
        filtered_scans = []
        for scan in scan_history:
            filtered_scans.append(scan)
            if scan.action == 'delivered':
                break
        scan_history = filtered_scans
        
    return render_template('dispatch/detail.html', parcel=parcel, scan_history=scan_history)

@dispatch_bp.route('/overdue')
@login_required
@permission_required('can_overdue')
def overdue_list():
    """All overdue parcels — due_date passed, still pending/in_transit."""
    from datetime import date
    from sqlalchemy import or_
    page = request.args.get('page', 1, type=int)

    query = Parcel.query.filter(
        Parcel.due_date != None,
        Parcel.due_date < date.today(),
        Parcel.status.in_(['pending', 'in_transit'])
    ).filter((Parcel.is_archived == False) | (Parcel.is_archived == None))

    if current_user.role == 'superadmin':
        pass  # sees all
    elif current_user.role == 'manager' and current_user.branch_id:
        query = query.filter(or_(
            Parcel.sender_branch_id == current_user.branch_id,
            Parcel.current_branch_id == current_user.branch_id,
            Parcel.receiver_branch_id == current_user.branch_id
        ))
    else:
        # Employee: STRICT match only — same as sidebar overdue_count
        strict_conds = [Parcel.created_by == current_user.id]
        if current_user.email and '@' in current_user.email and len(current_user.email.strip()) > 4:
            em = current_user.email.strip()
            strict_conds.append(Parcel.receiver_email.ilike(em))
            strict_conds.append(Parcel.sender_email.ilike(em))
        if current_user.name and len(current_user.name.strip()) > 2:
            nm = current_user.name.strip()
            strict_conds.append(Parcel.receiver_name.ilike(nm))
            strict_conds.append(Parcel.sender_name.ilike(nm))
        query = query.filter(or_(*strict_conds))

    parcels = query.order_by(Parcel.due_date.asc()).paginate(page=page, per_page=25, error_out=False)
    overdue_count = parcels.total

    return render_template('dispatch/overdue.html', parcels=parcels, overdue_count=overdue_count)

@dispatch_bp.route('/overdue/send-alerts', methods=['POST'])
@login_required
@permission_required('can_overdue')
def trigger_overdue_alerts():
    if current_user.role not in ['superadmin', 'manager']:
        flash('Permission denied.', 'error')
        return redirect(url_for('dispatch.overdue_list'))
        
    from datetime import date
    from app.models.parcel import Parcel
    from app.services.email_service import send_overdue_notification
    
    today = date.today()
    query = Parcel.query.filter(
        Parcel.due_date != None,
        Parcel.due_date < today,
        Parcel.status.in_(['pending', 'in_transit'])
    )
    
    # Non-superadmins only trigger for their branch
    if current_user.role not in ['superadmin']:
        user_cond = get_user_parcel_filter(current_user)
        if user_cond is not None:
            query = query.filter(user_cond)
        
    overdue_parcels = query.all()
    sent_count = 0
    for parcel in overdue_parcels:
        try:
            success = send_overdue_notification(
                parcel=parcel,
                base_url=current_app.config['BASE_URL'],
                company_name=current_app.config['COMPANY_NAME']
            )
            if success:
                parcel.overdue_email_sent = True
                parcel.last_overdue_email_sent = today
                sent_count += 1
        except Exception as e:
            print(f"Error sending manual overdue alert for {parcel.tracking_number}: {e}")
            
    if sent_count > 0:
        db.session.commit()
        flash(f"Successfully sent overdue email alerts for {sent_count} parcels to their senders & receivers!", 'success')
    else:
        flash("No overdue parcels found or alerts were not sent.", 'info')
        
    return redirect(url_for('dispatch.overdue_list'))


@dispatch_bp.route('/archive')
@login_required
@permission_required('can_archive')
def archive_list():
    """View all archived (delivered) parcels, filtered by branch for non-superadmin."""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    query = Parcel.query.filter_by(is_archived=True)

    if current_user.role != 'superadmin':
        user_cond = get_user_parcel_filter(current_user)
        if user_cond is not None:
            query = query.filter(user_cond)

    if search:
        query = query.filter(
            (Parcel.tracking_number.ilike(f'%{search}%')) |
            (Parcel.sender_name.ilike(f'%{search}%')) |
            (Parcel.receiver_name.ilike(f'%{search}%'))
        )

    parcels = query.order_by(Parcel.archived_at.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template('dispatch/archive.html', parcels=parcels, search=search)


@dispatch_bp.route('/archive/<int:parcel_id>', methods=['POST'])
@login_required
def archive_parcel(parcel_id):
    """Archive a delivered parcel. Only sender/creator or superadmin."""
    parcel = db.session.get(Parcel, parcel_id)
    if not parcel:
        return jsonify({'success': False, 'message': 'Parcel not found'}), 404

    # Only delivered/closed parcels can be archived
    if parcel.status not in ['delivered', 'closed', 'failed', 'returned']:
        return jsonify({'success': False, 'message': 'Only delivered/closed parcels can be archived'}), 403

    # Authorization: superadmin, creator, or same sender branch
    if current_user.role != 'superadmin':
        if parcel.created_by != current_user.id and current_user.branch_id != parcel.sender_branch_id:
            return jsonify({'success': False, 'message': 'Not authorized to archive this parcel'}), 403

    parcel.is_archived = True
    parcel.archived_at = datetime.utcnow()
    db.session.commit()
    
    from app.models.security_log import log_security_action
    log_security_action('parcel_archived', f"Archived parcel {parcel.tracking_number}.", user_id=current_user.id, username=current_user.username)
    
    return jsonify({'success': True, 'message': 'Parcel archived successfully'})


@dispatch_bp.route('/archive/delete-all', methods=['POST'])
@login_required
@permission_required('can_archive')
def delete_all_archived_parcels():
    """Permanently delete all archived parcels within the user's scope."""
    query = Parcel.query.filter_by(is_archived=True)
    if current_user.role != 'superadmin':
        user_cond = get_user_parcel_filter(current_user)
        if user_cond is not None:
            query = query.filter(user_cond)

    archived_parcels = query.all()
    count = len(archived_parcels)
    if count == 0:
        return jsonify({'success': False, 'message': 'No archived parcels found to delete.'}), 400

    parcel_ids = [p.id for p in archived_parcels]

    # Delete scan logs for these parcels
    ScanLog.query.filter(ScanLog.parcel_id.in_(parcel_ids)).delete(synchronize_session=False)

    # Delete the parcels
    for p in archived_parcels:
        db.session.delete(p)
    db.session.commit()

    from app.models.security_log import log_security_action
    log_security_action(
        'all_archived_parcels_deleted',
        f"Permanently deleted all {count} archived parcels.",
        user_id=current_user.id,
        username=current_user.username
    )

    return jsonify({
        'success': True,
        'count': count,
        'message': f'Successfully deleted all {count} archived parcel{"s" if count != 1 else ""} permanently.'
    })


@dispatch_bp.route('/unarchive/<int:parcel_id>', methods=['POST'])
@login_required
def unarchive_parcel(parcel_id):
    """Restore an archived parcel back to the active list."""
    parcel = db.session.get(Parcel, parcel_id)
    if not parcel:
        return jsonify({'success': False, 'message': 'Parcel not found'}), 404

    if current_user.role != 'superadmin':
        if parcel.created_by != current_user.id and current_user.branch_id != parcel.sender_branch_id:
            return jsonify({'success': False, 'message': 'Not authorized to unarchive this parcel'}), 403

    parcel.is_archived = False
    parcel.archived_at = None
    db.session.commit()
    
    from app.models.security_log import log_security_action
    log_security_action('parcel_unarchived', f"Restored parcel {parcel.tracking_number} from archive.", user_id=current_user.id, username=current_user.username)
    
    return jsonify({'success': True, 'message': 'Parcel restored from archive'})


@dispatch_bp.route('/delete/<int:parcel_id>', methods=['POST'])
@login_required
def delete_parcel(parcel_id):
    parcel = db.session.get(Parcel, parcel_id)
    if not parcel:
        return jsonify({'success': False, 'message': 'Parcel not found'}), 404
    
    # Collect all unique emails for cancellation notification before deleting
    all_emails = set()
    
    # 1. Direct fields on parcel
    if parcel.receiver_email and '@' in parcel.receiver_email:
        all_emails.add(parcel.receiver_email.strip())
    if parcel.sender_email and '@' in parcel.sender_email:
        all_emails.add(parcel.sender_email.strip())
        
    # 2. Branch emails — sirf us branch ka 1 email (branch login email), koi bhi staff users nahi
    if parcel.sender_branch and parcel.sender_branch.email and '@' in parcel.sender_branch.email:
        all_emails.add(parcel.sender_branch.email.strip())
    if parcel.receiver_branch and parcel.receiver_branch.email and '@' in parcel.receiver_branch.email:
        all_emails.add(parcel.receiver_branch.email.strip())


    # Store parcel info strings before deletion
    t_no = parcel.tracking_number
    s_name = parcel.sender_name or 'Sender'
    s_branch = parcel.sender_branch.name if parcel.sender_branch else 'Source Branch'
    r_name = parcel.receiver_name or 'Receiver'
    r_branch = parcel.receiver_branch.name if parcel.receiver_branch else 'Destination Branch'
    cancelled_by_str = f"{current_user.name} ({current_user.branch_name or 'Office'})"

    # Send cancellation notification email to all relevant parties
    for email_addr in all_emails:
        try:
            send_parcel_cancellation_notification(
                to_email=email_addr,
                name='Team',
                tracking_number=t_no,
                sender_name=s_name,
                sender_branch=s_branch,
                receiver_name=r_name,
                receiver_branch=r_branch,
                cancelled_by=cancelled_by_str,
                company_name=current_app.config['COMPANY_NAME']
            )
        except Exception as e:
            print(f"[CANCELLATION EMAIL ERROR] Failed to send to {email_addr}: {e}")

    # Delete scan logs
    ScanLog.query.filter_by(parcel_id=parcel.id).delete()
    
    # Delete parcel
    db.session.delete(parcel)
    db.session.commit()
    
    from app.models.security_log import log_security_action
    log_security_action('parcel_deleted', f"Deleted parcel {t_no} and cancelled dispatch.", user_id=current_user.id, username=current_user.username)
    
    return jsonify({'success': True, 'message': 'Parcel deleted and cancellation emails dispatched successfully'})

@dispatch_bp.route('/edit/<tracking_number>', methods=['GET', 'POST'])
@login_required
def edit_dispatch(tracking_number):
    from app.models.item import Item
    parcel = Parcel.query.filter_by(tracking_number=tracking_number).first_or_404()
    
    # Check authorization: superadmin, or the person who created (sent) the parcel
    if current_user.role != 'superadmin':
        if parcel.created_by != current_user.id and current_user.branch_id != parcel.sender_branch_id:
            flash('You are not authorized to edit this dispatch. Only the sender can edit their parcel.', 'error')
            return redirect(url_for('dispatch.dispatch_detail', tracking_number=tracking_number))
            
    branches = Branch.query.filter_by(is_active=True).order_by(Branch.name).all()
    users = User.query.filter(User.is_active == True).order_by(User.name).all()
    items = Item.query.order_by(Item.name).all()
    
    if request.method == 'POST':
        try:
            # Handle additional photo uploads
            photos = list(parcel.photos)
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], tracking_number)
            os.makedirs(upload_dir, exist_ok=True)
            
            for photo_file in request.files.getlist('photos'):
                if photo_file and photo_file.filename and allowed_file(photo_file.filename):
                    fname = secure_filename(photo_file.filename)
                    save_path = os.path.join(upload_dir, fname)
                    photo_file.save(save_path)
                    photos.append(f'/static/uploads/{tracking_number}/{fname}')
            
            parcel.photos = photos
            
            # Update Sender details
            parcel.sender_name = request.form.get('sender_name', parcel.sender_name)
            parcel.sender_phone = request.form.get('sender_phone', parcel.sender_phone)
            parcel.sender_email = request.form.get('sender_email', parcel.sender_email)
            parcel.sender_address = request.form.get('sender_address', parcel.sender_address)
            
            # Only superadmins can edit the source branch
            if current_user.role == 'superadmin':
                sender_branch_id = request.form.get('sender_branch_id')
                if sender_branch_id:
                    parcel.sender_branch_id = int(sender_branch_id)
            
            # Update Receiver details
            parcel.receiver_name = request.form.get('receiver_name', parcel.receiver_name)
            parcel.receiver_phone = request.form.get('receiver_phone', parcel.receiver_phone)
            parcel.receiver_email = request.form.get('receiver_email', parcel.receiver_email)
            parcel.receiver_address = request.form.get('receiver_address', parcel.receiver_address)
            
            receiver_branch_id = request.form.get('receiver_branch_id')
            if receiver_branch_id:
                parcel.receiver_branch_id = int(receiver_branch_id)
                
            # Update Package details
            description = request.form.get('description', '')
            if description:
                parcel.description = description
                
            parcel.priority = request.form.get('priority', parcel.priority).lower()
            raw_w = float(request.form.get('weight', parcel.weight) or 0)
            parcel.weight = raw_w / 1000.0 if request.form.get('weight_unit', 'kg').lower() == 'gms' else raw_w
            
            transfer_mode = request.form.get('transfer_mode', parcel.transfer_mode)
            parcel.transfer_mode = transfer_mode
            
            parcel.courier_partner = (request.form.get('other_courier_name', '').strip() if request.form.get('courier_partner') == 'Other Company' else request.form.get('courier_partner', '')) if transfer_mode == 'by_courier' else ''
            parcel.courier_id = request.form.get('courier_id', '') if transfer_mode == 'by_courier' else ''
            parcel.bus_number = request.form.get('bus_number', '') if transfer_mode == 'by_bus' else ''
            parcel.driver_phone = request.form.get('driver_phone', '') if transfer_mode == 'by_bus' else ''
            parcel.hand_carry_name = request.form.get('hand_carry_name', '') if transfer_mode == 'by_hand' else ''
            parcel.hand_carry_phone = request.form.get('hand_carry_phone', '') if transfer_mode == 'by_hand' else ''
            
            parcel.billing_amount = float(request.form.get('billing_amount', parcel.billing_amount) or 0)
            parcel.special_instructions = request.form.get('special_instructions', parcel.special_instructions)
            
            # Update optional due date
            due_date_str = request.form.get('due_date', '')
            if due_date_str:
                try:
                    parcel.due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            else:
                parcel.due_date = None
                
            # Create a scan log for the edit action
            user_identifier = current_user.email if current_user.email else current_user.username
            branch = db.session.get(Branch, current_user.branch_id) if current_user.branch_id else None
            scan_log = ScanLog(
                parcel_id=parcel.id,
                tracking_number=parcel.tracking_number,
                branch_id=current_user.branch_id,
                branch_name=branch.name if branch else 'Web App',
                employee_id=current_user.id,
                employee_name=f"{current_user.name} ({user_identifier})",
                action='edited',
                notes=f"Parcel details edited by {current_user.name}"
            )
            db.session.add(scan_log)
            db.session.commit()
            
            from app.models.security_log import log_security_action
            log_security_action('parcel_edited', f"Edited parcel details for {tracking_number}.", user_id=current_user.id, username=current_user.username)
            
            flash('Parcel details updated successfully!', 'success')
            return redirect(url_for('dispatch.dispatch_detail', tracking_number=tracking_number))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating dispatch details: {str(e)}', 'error')
            
    return render_template('dispatch/edit.html', parcel=parcel, branches=branches, users=users, items=items)


# ─────────────────────────────────────────────────────────────────────────────
#  DISPATCH QUERY WORKFLOW  (Department → Admin → Receiver → Sender)
# ─────────────────────────────────────────────────────────────────────────────

@dispatch_bp.route('/query/new', methods=['GET', 'POST'])
@login_required
@permission_required('can_raise_query')
def raise_query():
    """Department employee raises a new dispatch query/request."""
    branches    = Branch.query.filter_by(is_active=True).order_by(Branch.name).all()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    users       = User.query.filter(User.is_active == True).order_by(User.name).all()

    # Fetch Admin Employees strictly (Ramji Lal & Ravi only for pickup assignment)
    admin_employees = User.query.filter(
        User.is_active == True,
        db.or_(
            User.name.ilike('%ravi%'),
            User.name.ilike('%ramji%')
        )
    ).order_by(User.name).all()

    if request.method == 'POST':
        try:
            tracking_number = generate_tracking_number()
            while Parcel.query.filter_by(tracking_number=tracking_number).first():
                tracking_number = generate_tracking_number()

            qr_result = generate_qr_code(tracking_number, current_app.config['BASE_URL'])

            # Sender defaults to current user's branch + department
            sender_branch_id     = current_user.branch_id
            sender_department_id = current_user.department_id or request.form.get('sender_department_id')
            sender_branch        = db.session.get(Branch,     int(sender_branch_id))     if sender_branch_id     else None
            sender_department    = db.session.get(Department, int(sender_department_id)) if sender_department_id else None

            # Handle Destination Branch / Other Location
            receiver_branch_id = request.form.get('receiver_branch_id')
            if receiver_branch_id == 'other':
                receiver_branch_id = None
                receiver_branch = None
                receiver_branch_name = request.form.get('other_receiver_location', '').strip()
            else:
                receiver_branch = db.session.get(Branch, int(receiver_branch_id)) if receiver_branch_id else None
                receiver_branch_name = receiver_branch.name if receiver_branch else ''

            receiver_department_id = request.form.get('receiver_department_id')
            receiver_department    = db.session.get(Department, int(receiver_department_id)) if receiver_department_id else None

            assigned_admin_id = request.form.get('assigned_admin_id')

            parcel = Parcel(
                tracking_number=tracking_number,
                qr_code_path=qr_result['qr_path'],
                # Sender
                sender_name=request.form.get('sender_name', current_user.name),
                sender_phone=request.form.get('sender_phone', current_user.phone or ''),
                sender_email=request.form.get('sender_email', current_user.email or ''),
                sender_address=request.form.get('sender_address', ''),
                sender_branch_id=sender_branch_id,
                sender_department_id=int(sender_department_id) if sender_department_id else None,
                sender_department_name=sender_department.name if sender_department else '',
                # Receiver
                receiver_name=request.form.get('receiver_name', ''),
                receiver_phone=request.form.get('receiver_phone', ''),
                receiver_email=request.form.get('receiver_email', ''),
                receiver_address=request.form.get('receiver_address', ''),
                receiver_branch_id=int(receiver_branch_id) if receiver_branch_id else None,
                receiver_branch_name=receiver_branch_name,
                receiver_department_id=int(receiver_department_id) if receiver_department_id else None,
                receiver_department_name=receiver_department.name if receiver_department else '',
                # Package
                description=request.form.get('description', ''),
                priority=request.form.get('priority', 'normal').lower(),
                special_instructions=request.form.get('special_instructions', ''),
                # Workflow status
                status='query_raised',
                current_branch_id=sender_branch_id,
                created_by=current_user.id,
                assigned_admin_id=int(assigned_admin_id) if assigned_admin_id else None,
                dispatched_at=datetime.utcnow(),
            )
            db.session.add(parcel)
            db.session.flush()

            # Initial scan log
            scan_log = ScanLog(
                parcel_id=parcel.id,
                tracking_number=tracking_number,
                branch_id=sender_branch.id if sender_branch else None,
                branch_name=sender_branch.name if sender_branch else current_user.branch_name,
                employee_id=current_user.id,
                employee_name=current_user.name,
                action='query_raised',
                notes=f'Dispatch query raised by {current_user.name} ({sender_department.name if sender_department else "Department"})'
            )
            db.session.add(scan_log)
            db.session.commit()

            # --- Send email notifications ---
            # 1. Notify the sender
            s_email = current_user.email
            if s_email and '@' in s_email:
                try:
                    from app.services.email_service import send_query_raised_notification
                    send_query_raised_notification(
                        sender_email=s_email,
                        sender_name=current_user.name,
                        tracking_number=tracking_number,
                        receiver_name=parcel.receiver_name,
                        receiver_branch=receiver_branch_name or 'Destination Office',
                        company_name=current_app.config['COMPANY_NAME']
                    )
                except Exception as e:
                    print(f"Error sending sender query raised email: {e}")

            # 2. Notify the assigned Admin Department employee directly
            if assigned_admin_id:
                try:
                    from app.services.email_service import send_query_pickup_alert_to_admin
                    assigned_admin_user = db.session.get(User, int(assigned_admin_id))
                    if assigned_admin_user and assigned_admin_user.email and '@' in assigned_admin_user.email:
                        send_query_pickup_alert_to_admin(
                            admin_email=assigned_admin_user.email.strip(),
                            sender_name=current_user.name,
                            sender_department=sender_department.name if sender_department else 'Department',
                            sender_branch=sender_branch.name if sender_branch else 'Office',
                            tracking_number=tracking_number,
                            company_name=current_app.config['COMPANY_NAME']
                        )
                except Exception as e:
                    print(f"Error sending admin query raised email: {e}")

            flash(f'Dispatch query raised successfully! Tracking ID: {tracking_number}', 'success')
            return redirect(url_for('dispatch.my_queries'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error raising query: {str(e)}', 'error')

    return render_template('dispatch/query_new.html',
                           branches=branches, departments=departments, users=users,
                           admin_employees=admin_employees)


@dispatch_bp.route('/queries')
@login_required
@permission_required('can_raise_query')
def my_queries():
    """Department employee: list their own dispatch queries."""
    page   = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')

    query = Parcel.query.filter_by(created_by=current_user.id)
    # only show workflow statuses in this view
    query = query.filter(Parcel.status.in_(
        ['query_raised', 'picked_up', 'in_transit', 'delivered_pending', 'closed', 'failed']
    ))

    if status:
        query = query.filter_by(status=status)

    parcels = query.order_by(Parcel.dispatched_at.desc()).paginate(page=page, per_page=25, error_out=False)

    # count pending-confirmation items for badge
    pending_confirm_count = Parcel.query.filter_by(
        created_by=current_user.id, status='delivered_pending'
    ).count()

    return render_template('dispatch/queries_list.html',
                           parcels=parcels, status=status,
                           pending_confirm_count=pending_confirm_count)


@dispatch_bp.route('/query/confirm/<int:parcel_id>', methods=['POST'])
@login_required
@permission_required('can_raise_query')
def confirm_query(parcel_id):
    """Sender confirms delivery — closes the query."""
    parcel = db.session.get(Parcel, parcel_id)
    if not parcel:
        flash('Query not found.', 'error')
        return redirect(url_for('dispatch.my_queries'))

    if parcel.created_by != current_user.id:
        flash('You are not authorised to confirm this query.', 'error')
        return redirect(url_for('dispatch.my_queries'))

    if parcel.status != 'delivered_pending':
        flash('This query is not in a state that can be confirmed yet.', 'error')
        return redirect(url_for('dispatch.my_queries'))

    try:
        parcel.status = 'closed'
        parcel.is_archived = True
        parcel.archived_at = datetime.utcnow()
        scan_log = ScanLog(
            parcel_id=parcel.id,
            tracking_number=parcel.tracking_number,
            branch_id=current_user.branch_id,
            branch_name=current_user.branch_name or 'Office',
            employee_id=current_user.id,
            employee_name=current_user.name,
            action='closed',
            notes=f'Delivery confirmed and query closed by sender: {current_user.name}'
        )
        db.session.add(scan_log)
        db.session.commit()

        # Send final confirmation email to both Sender & Receiver
        try:
            from app.services.email_service import send_query_closed_notification
            send_query_closed_notification(
                sender_email=parcel.sender_email or current_user.email,
                receiver_email=parcel.receiver_email,
                tracking_number=parcel.tracking_number,
                receiver_name=parcel.receiver_name,
                company_name=current_app.config['COMPANY_NAME']
            )
        except Exception as e:
            print(f"Error sending query closed confirmation email: {e}")

        flash('Query confirmed and closed successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error confirming query: {str(e)}', 'error')

    return redirect(url_for('dispatch.my_queries'))


@dispatch_bp.route('/bulk/template')
@login_required
def download_bulk_template():
    import openpyxl
    from io import BytesIO
    from flask import make_response
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Bulk Dispatch Template"
    
    headers = [
        "Sender Name", "Sender Phone", "Sender Email", "Sender Address",
        "Receiver Name", "Receiver Phone", "Receiver Email", "Receiver Address",
        "Receiver Branch Code", "Receiver Department Code", "Item Description",
        "Priority", "Weight (kg)", "Transfer Mode", "Courier Company",
        "Docket / AWB Number", "Bus Number", "Driver Mobile Number",
        "Hand Carry Name", "Hand Carry Mobile"
    ]
    ws.append(headers)
    
    # Add a sample row
    sample_row = [
        "Amit Sharma", "9876543210", "amit@company.com", "Jaipur Office",
        "Rakesh Verma", "9829012345", "rakesh@company.com", "Delhi Office Main Building",
        "DL", "ACC", "Urgent Accounts Files & Vouchers",
        "Urgent", "1.5", "By Courier", "Blue Dart",
        "BD12345678", "", "",
        "", ""
    ]
    ws.append(sample_row)
    
    # Style the headers to look premium
    from openpyxl.styles import Font, PatternFill, Alignment
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0A0F1E", end_color="0A0F1E", fill_type="solid")
    
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        # Auto-fit columns
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = max(len(headers[col_idx-1]) + 4, 15)
        
    out = BytesIO()
    wb.save(out)
    excel_bytes = out.getvalue()
    
    response = make_response(excel_bytes)
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    response.headers["Content-Disposition"] = "attachment; filename=Bulk_Dispatch_Template.xlsx"
    response.headers["Content-Length"] = str(len(excel_bytes))
    return response


@dispatch_bp.route('/bulk', methods=['GET', 'POST'])
@login_required
@permission_required('can_bulk_dispatch')
def bulk_dispatch():
    from app.models.branch import Branch
    from app.models.department import Department
    from app.models.parcel import Parcel, generate_tracking_number, get_user_parcel_filter
    from app.models.scan_log import ScanLog
    from app.services.qr_service import generate_qr_code
    from app.services.email_service import (
        get_dispatch_receiver_email_data,
        get_dispatch_sender_email_data,
        send_bulk_dispatch_emails_background
    )
    from app.models.security_log import log_security_action
    import openpyxl
    from flask import current_app
    
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or file.filename == '':
            flash('No file uploaded. Please select an Excel file.', 'error')
            return redirect(url_for('dispatch.bulk_dispatch'))
            
        if not file.filename.endswith('.xlsx'):
            flash('Invalid file format. Please upload an Excel (.xlsx) file.', 'error')
            return redirect(url_for('dispatch.bulk_dispatch'))
            
        try:
            # High-speed read-only streaming parser (memory safe)
            wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
            ws = wb.active
            
            rows_iter = ws.iter_rows(values_only=True)
            try:
                first_row = next(rows_iter)
            except StopIteration:
                first_row = None
                
            if not first_row or not any(first_row):
                wb.close()
                flash('The spreadsheet is empty or has no data rows.', 'error')
                return redirect(url_for('dispatch.bulk_dispatch'))
                
            headers = [str(h).strip().lower() for h in first_row if h is not None]
            required_cols = [
                "sender name", "receiver name", "receiver email", 
                "receiver branch code", "item description"
            ]
            for col in required_cols:
                if col not in headers:
                    wb.close()
                    flash(f"Missing required column in Excel: '{col}'", 'error')
                    return redirect(url_for('dispatch.bulk_dispatch'))
                    
            # High-performance in-memory cache for branch & department lookups
            active_branches = {b.branch_code.strip().upper(): b for b in Branch.query.filter_by(is_active=True).all()}
            active_depts = {d.code.strip().upper(): d for d in Department.query.filter_by(is_active=True).all()}

            errors = []
            valid_parcels_data = []
            
            row_idx = 1
            consecutive_empty = 0
            for row in rows_iter:
                row_idx += 1
                # Check if row has any non-blank cells
                if not any(str(c).strip() != '' for c in row if c is not None):
                    consecutive_empty += 1
                    if consecutive_empty >= 5:
                        break
                    continue
                    
                row_dict = {}
                for idx, val in enumerate(row):
                    if idx < len(headers):
                        row_dict[headers[idx]] = val
                
                s_name = str(row_dict.get('sender name') or '').strip()
                r_name = str(row_dict.get('receiver name') or '').strip()
                r_email = str(row_dict.get('receiver email') or '').strip()
                desc = str(row_dict.get('item description') or '').strip()
                b_code = str(row_dict.get('receiver branch code') or '').strip().upper()

                # If all primary parcel fields are empty, this is a blank/trailing row
                if not s_name and not r_name and not r_email and not desc and not b_code:
                    consecutive_empty += 1
                    if consecutive_empty >= 5:
                        break
                    continue

                consecutive_empty = 0
                row_errors = []
                
                if not s_name:
                    row_errors.append(f"Row {row_idx}: Sender Name is missing.")
                if not r_name:
                    row_errors.append(f"Row {row_idx}: Receiver Name is missing.")
                if not r_email or '@' not in r_email:
                    row_errors.append(f"Row {row_idx}: Valid Receiver Email is required.")
                if not desc:
                    row_errors.append(f"Row {row_idx}: Item Description is missing.")
                if not b_code:
                    row_errors.append(f"Row {row_idx}: Receiver Branch Code is missing.")
                else:
                    branch = active_branches.get(b_code)
                    if not branch:
                        row_errors.append(f"Row {row_idx}: Receiver Branch Code '{b_code}' is invalid or inactive.")
                    else:
                        row_dict['receiver_branch_obj'] = branch
                        
                dept_code = str(row_dict.get('receiver department code') or '').strip().upper()
                if dept_code:
                    dept = active_depts.get(dept_code)
                    if not dept:
                        row_errors.append(f"Row {row_idx}: Department Code '{dept_code}' is invalid or inactive.")
                    else:
                        row_dict['receiver_department_obj'] = dept
                else:
                    row_dict['receiver_department_obj'] = None
                    
                weight_val = 0.0
                weight_str = str(row_dict.get('weight (kg)') or '0').strip()
                try:
                    if weight_str:
                        weight_val = float(weight_str)
                except ValueError:
                    row_errors.append(f"Row {row_idx}: Weight must be a numeric value.")
                row_dict['weight_val'] = weight_val
                
                if row_errors:
                    errors.extend(row_errors)
                else:
                    valid_parcels_data.append(row_dict)
                    
            wb.close()
            if errors:
                return render_template('dispatch/bulk_upload.html', errors=errors)

            if not valid_parcels_data:
                flash('No valid data rows found to dispatch.', 'error')
                return redirect(url_for('dispatch.bulk_dispatch'))

            # Batch unique tracking number generation
            needed = len(valid_parcels_data)
            candidate_pool = set()
            while len(candidate_pool) < needed:
                candidate_pool.add(generate_tracking_number())
            existing_numbers = set(
                r[0] for r in db.session.query(Parcel.tracking_number).filter(
                    Parcel.tracking_number.in_(list(candidate_pool))
                ).all()
            )
            candidate_pool = list(candidate_pool - existing_numbers)
            while len(candidate_pool) < needed:
                t = generate_tracking_number()
                if t not in candidate_pool:
                    candidate_pool.append(t)
            tracking_numbers = candidate_pool[:needed]

            # Fast batch creation & single atomic commit
            company = current_app.config['COMPANY_NAME']
            base_url = current_app.config['BASE_URL']
            app_cfg = dict(current_app.config)

            created_tracking_numbers = []
            parcels_created = []
            email_items = []
            now = datetime.utcnow()

            for idx, item in enumerate(valid_parcels_data):
                tracking_number = tracking_numbers[idx]
                qr_result = generate_qr_code(tracking_number, base_url)
                
                dest_branch = item['receiver_branch_obj']
                dest_dept = item['receiver_department_obj']
                
                t_mode_raw = str(item.get('transfer_mode') or 'By Courier').strip().lower()
                t_mode = 'by_courier'
                if 'bus' in t_mode_raw:
                    t_mode = 'by_bus'
                elif 'hand' in t_mode_raw:
                    t_mode = 'by_hand'
                    
                p = Parcel(
                    tracking_number=tracking_number,
                    qr_code_path=qr_result['qr_path'],
                    sender_name=str(item.get('sender name') or '').strip(),
                    sender_phone=str(item.get('sender phone') or '').strip(),
                    sender_email=str(item.get('sender email') or '').strip(),
                    sender_address=str(item.get('sender address') or '').strip(),
                    sender_branch_id=current_user.branch_id,
                    sender_department_id=current_user.department_id,
                    sender_department_name=current_user.department.name if current_user.department else '',
                    
                    receiver_name=str(item.get('receiver name') or '').strip(),
                    receiver_phone=str(item.get('receiver phone') or '').strip(),
                    receiver_email=str(item.get('receiver email') or '').strip(),
                    receiver_address=str(item.get('receiver address') or '').strip(),
                    receiver_branch_id=dest_branch.id,
                    receiver_branch_name=dest_branch.name,
                    receiver_department_id=dest_dept.id if dest_dept else None,
                    receiver_department_name=dest_dept.name if dest_dept else '',
                    
                    description=str(item.get('item description') or '').strip(),
                    priority=str(item.get('priority') or 'normal').strip().lower(),
                    weight=item['weight_val'],
                    transfer_mode=t_mode,
                    courier_partner=str(item.get('courier company') or '').strip(),
                    courier_id=str(item.get('docket / awb number') or '').strip(),
                    bus_number=str(item.get('bus number') or '').strip(),
                    driver_phone=str(item.get('driver mobile number') or '').strip(),
                    hand_carry_name=str(item.get('hand carry name') or '').strip(),
                    hand_carry_phone=str(item.get('hand carry mobile') or '').strip(),
                    status='pending',
                    current_branch_id=current_user.branch_id,
                    created_by=current_user.id,
                    dispatched_at=now
                )
                db.session.add(p)
                parcels_created.append((p, dest_branch))
                created_tracking_numbers.append(tracking_number)

            # Single flush to populate parcel IDs
            db.session.flush()

            # Create scan logs and prepare emails
            for p, dest_branch in parcels_created:
                scan_log = ScanLog(
                    parcel_id=p.id,
                    tracking_number=p.tracking_number,
                    branch_id=current_user.branch_id,
                    branch_name=current_user.branch_name or 'Web App',
                    employee_id=current_user.id,
                    employee_name=current_user.name,
                    action='dispatched',
                    notes='File bulk dispatched'
                )
                db.session.add(scan_log)

                # Prepare emails for background delivery
                # 1. Receiver notification
                if p.receiver_email:
                    r_data = get_dispatch_receiver_email_data(
                        receiver_email=p.receiver_email,
                        receiver_name=p.receiver_name,
                        tracking_number=p.tracking_number,
                        sender_name=p.sender_name,
                        sender_branch=current_user.branch_name or 'Source Branch',
                        receiver_branch=dest_branch.name,
                        transfer_mode=p.transfer_mode_label,
                        courier_partner=p.courier_partner,
                        company_name=company,
                        base_url=base_url,
                        courier_id=p.courier_id
                    )
                    if r_data: email_items.append(r_data)

                # NOTE: Sender confirmation on dispatch removed as requested.
                # (Only receiver gets notified on dispatch)

            # Commit all database transactions atomically in one shot
            db.session.commit()

            # Trigger background email delivery over persistent connection
            if email_items:
                send_bulk_dispatch_emails_background(email_items, app_cfg)

            # Log security action
            log_security_action('bulk_upload', f"Uploaded bulk dispatches: {', '.join(created_tracking_numbers[:5])}... ({len(created_tracking_numbers)} total)", user_id=current_user.id, username=current_user.username)
            
            flash(f"Successfully uploaded and dispatched {len(created_tracking_numbers)} parcels!", 'success')
            from flask import session as flask_session
            flask_session['bulk_tracking_numbers'] = created_tracking_numbers
            return redirect(url_for('dispatch.bulk_success'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error parsing Excel file: {str(e)}", 'error')
            return redirect(url_for('dispatch.bulk_dispatch'))
            
    return render_template('dispatch/bulk_upload.html')



@dispatch_bp.route('/bulk/success')
@login_required
def bulk_success():
    from flask import session as flask_session
    tracking_numbers = flask_session.get('bulk_tracking_numbers', [])
    if not tracking_numbers:
        flash('No bulk dispatch session found. Please upload again.', 'warning')
        return redirect(url_for('dispatch.bulk_dispatch'))
    parcels = Parcel.query.filter(Parcel.tracking_number.in_(tracking_numbers)).order_by(Parcel.id.asc()).all()
    return render_template('dispatch/bulk_success.html', parcels=parcels, total=len(parcels))


@dispatch_bp.route('/bulk/print-labels')
@login_required
def bulk_print_labels():
    from flask import session as flask_session
    tracking_numbers = flask_session.get('bulk_tracking_numbers', [])
    if not tracking_numbers:
        flash('No bulk dispatch session found. Please upload a new batch.', 'warning')
        return redirect(url_for('dispatch.bulk_dispatch'))
    parcels = Parcel.query.filter(Parcel.tracking_number.in_(tracking_numbers)).order_by(Parcel.id.asc()).all()
    return render_template('dispatch/bulk_print_labels.html', parcels=parcels)
