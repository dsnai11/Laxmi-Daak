from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app import db, socketio
from app.models.parcel import Parcel, user_can_view_parcel
from app.models.scan_log import ScanLog
from app.models.branch import Branch
from app.services.email_service import send_arrival_notification, send_delivery_notification, send_failed_notification
from datetime import datetime
from flask import current_app
import os
from werkzeug.utils import secure_filename

scan_bp = Blueprint('scan', __name__, url_prefix='/scan')

@scan_bp.before_request
@login_required
def check_scan_access():
    from flask import abort
    if current_user.role != 'superadmin' and current_user.role != 'manager' and not current_user.has_permission('can_scan'):
        abort(403)


SCAN_ACTIONS = {'received', 'out_for_delivery', 'delivered', 'failed', 'returned'}

ALLOWED_PHOTO_EXTENSIONS ={'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

def _allowed_photo(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS

@scan_bp.route('')
@scan_bp.route('/')
@login_required
def scanner():
    return render_template('scan/scanner.html')

@scan_bp.route('/lookup/<tracking_number>')
@login_required
def lookup(tracking_number):
    parcel = Parcel.query.filter_by(tracking_number=tracking_number.upper()).first()
    if not parcel:
        return jsonify({'success': False, 'message': 'Parcel not found'}), 404
    
    scan_history = ScanLog.query.filter_by(parcel_id=parcel.id).order_by(ScanLog.timestamp.asc()).all()
    
    receiver_branch_name = ''
    if parcel.receiver_branch_id:
        rb = db.session.get(Branch, parcel.receiver_branch_id)
        receiver_branch_name = rb.name if rb else ''
    
    # Any scanner may identify a parcel in transit, but contact details and
    # contents are only shown to people inside the parcel's scope.
    in_scope = user_can_view_parcel(current_user, parcel)

    return jsonify({
        'success': True,
        'parcel': {
            'id': parcel.id,
            'tracking_number': parcel.tracking_number,
            'sender_name': parcel.sender_name,
            'sender_phone': (parcel.sender_phone or '') if in_scope else '',
            'sender_email': (parcel.sender_email or '') if in_scope else '',
            'receiver_name': parcel.receiver_name,
            'receiver_phone': (parcel.receiver_phone or '') if in_scope else '',
            'receiver_email': (parcel.receiver_email or '') if in_scope else '',
            'receiver_branch': receiver_branch_name,
            'description': (parcel.description or '') if in_scope else '',
            'priority': parcel.priority,
            'priority_label': parcel.priority_label,
            'status': parcel.status,
            'status_label': parcel.status_label,
            'current_branch': parcel.current_branch.name if parcel.current_branch else 'Unknown',
            'dispatched_at': parcel.dispatched_at.strftime('%Y-%m-%d %H:%M') if parcel.dispatched_at else ''
        },
        'scan_history': [
            {
                'action': s.action_label,
                'action_icon': s.action_icon,
                'branch': s.branch_name,
                'employee': s.employee_name,
                'timestamp': s.timestamp.strftime('%Y-%m-%d %H:%M'),
                'notes': s.notes
            } for s in scan_history
        ]
    })

@scan_bp.route('/process', methods=['POST'])
@login_required
def process_scan():
    # /api/scan reaches this function without the blueprint-level check
    if current_user.role not in ('superadmin', 'manager') and not current_user.has_permission('can_scan'):
        return jsonify({'success': False, 'message': 'Not authorized to scan'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    tracking_number = (data.get('tracking_number', '') or '').strip().upper()
    action = data.get('action', 'received')
    notes = data.get('notes', '')

    if not tracking_number:
        return jsonify({'success': False, 'message': 'Tracking number required'}), 400
    if action not in SCAN_ACTIONS:
        return jsonify({'success': False, 'message': 'Invalid scan action'}), 400

    parcel = Parcel.query.filter_by(tracking_number=tracking_number).first()
    if not parcel:
        return jsonify({'success': False, 'message': f'Parcel {tracking_number} not found'}), 404

    # Query-workflow parcels are handled by the admin pickup/confirm flow, not by scans
    if parcel.status in ('query_raised', 'closed') and current_user.role != 'superadmin':
        return jsonify({'success': False, 'message': 'This parcel cannot be updated by scanning in its current state.'}), 400

    # Any branch may log a hand-over (received / out for delivery), but closing
    # a parcel out as delivered, failed or returned needs the parcel to be in
    # the user's scope (sender, receiver or current branch, or personally theirs).
    if action in ('delivered', 'failed', 'returned') and not user_can_view_parcel(current_user, parcel):
        return jsonify({'success': False, 'message': 'You are not authorized to update this parcel.'}), 403

    try:
        # Update parcel status and current branch
        old_status = parcel.status
        status_map = {
            'received': 'in_transit',
            'out_for_delivery': 'in_transit',
            'delivered': 'delivered',
            'failed': 'failed',
            'returned': 'returned'
        }
        
        if action == 'delivered':
            # Only receiver/destination branch or superadmin can mark as delivered
            if current_user.role != 'superadmin' and parcel.receiver_branch_id and current_user.branch_id != parcel.receiver_branch_id:
                return jsonify({
                    'success': False,
                    'message': 'Only the destination/receiver branch can mark this parcel as delivered.'
                }), 400
            new_status = 'delivered'
            parcel.delivered_at = datetime.utcnow()
            parcel.is_archived = True
            parcel.archived_at = datetime.utcnow()
        else:
            new_status = status_map.get(action, parcel.status)
            if new_status == 'delivered':
                parcel.is_archived = True
                parcel.archived_at = datetime.utcnow()
            
        parcel.status = new_status
        
        if current_user.branch_id:
            parcel.current_branch_id = current_user.branch_id
        
        # Create scan log
        branch = db.session.get(Branch, current_user.branch_id) if current_user.branch_id else None
        user_identifier = current_user.email if current_user.email else (current_user.username if current_user.username else current_user.name)
        display_emp_name = f"{current_user.name} ({user_identifier})" if (current_user.email and current_user.name != current_user.email) else user_identifier
        
        scan_log = ScanLog(
            parcel_id=parcel.id,
            tracking_number=tracking_number,
            branch_id=current_user.branch_id,
            branch_name=branch.name if branch else current_user.branch_name,
            employee_id=current_user.id,
            employee_name=display_emp_name,
            action=action,
            notes=notes,
            timestamp=datetime.utcnow()
        )
        db.session.add(scan_log)
        db.session.commit()
        
        from app.models.security_log import log_security_action
        log_security_action('scan_recorded', f"Scanned parcel {tracking_number} with action: {action}.", user_id=current_user.id, username=current_user.username)
        
        # Emit Socket.IO event for real-time dashboard update
        socketio.emit('scan_update', {
            'tracking_number': tracking_number,
            'action': action,
            'action_label': scan_log.action_label,
            'branch': scan_log.branch_name,
            'employee': current_user.name,
            'timestamp': scan_log.timestamp.strftime('%H:%M:%S'),
            'status': new_status
        })
        
        # Send email notification
        try:
            company = current_app.config['COMPANY_NAME']
            base_url = current_app.config['BASE_URL']
            if action == 'received' and parcel.receiver_email:
                send_arrival_notification(parcel.receiver_email, parcel.receiver_name, tracking_number, scan_log.branch_name, company, base_url)
            elif action == 'delivered':
                if parcel.sender_email:
                    send_delivery_notification(parcel.sender_email, parcel.receiver_email, tracking_number, parcel.receiver_name, company, base_url)
            elif action == 'failed' and parcel.sender_email:
                send_failed_notification(parcel.sender_email, parcel.sender_name, tracking_number, company, base_url)
        except Exception:
            pass
        
        return jsonify({
            'success': True,
            'message': f'Parcel {tracking_number} marked as {scan_log.action_label}',
            'new_status': new_status,
            'status_label': parcel.status_label
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@scan_bp.route('/upload-photo', methods=['POST'])
@login_required
def upload_scan_photo():
    """Optional: upload a proof-of-delivery photo after a scan action."""
    tracking_number = (request.form.get('tracking_number') or '').strip().upper()
    if not tracking_number:
        return jsonify({'success': False, 'message': 'Tracking number required'}), 400

    photo_file = request.files.get('photo')
    if not photo_file or not photo_file.filename:
        return jsonify({'success': False, 'message': 'No photo file provided'}), 400

    if not _allowed_photo(photo_file.filename):
        return jsonify({'success': False, 'message': 'Invalid file type. Allowed: jpg, png, gif, webp'}), 400

    parcel = Parcel.query.filter_by(tracking_number=tracking_number).first()
    if not parcel:
        return jsonify({'success': False, 'message': f'Parcel {tracking_number} not found'}), 404
    if not user_can_view_parcel(current_user, parcel):
        return jsonify({'success': False, 'message': 'You are not authorized to add photos to this parcel.'}), 403

    try:
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], tracking_number)
        os.makedirs(upload_dir, exist_ok=True)

        # Prefix with 'scan_' to distinguish from dispatch photos
        fname = f"scan_{secure_filename(photo_file.filename)}"
        save_path = os.path.join(upload_dir, fname)
        photo_file.save(save_path)

        # Append to parcel photos list
        photos = list(parcel.photos)
        photos.append(f'/static/uploads/{tracking_number}/{fname}')
        parcel.photos = photos
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Photo uploaded successfully',
            'photo_url': f'/static/uploads/{tracking_number}/{fname}'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
