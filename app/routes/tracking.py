from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user, login_required
from app.models.parcel import Parcel
from app.models.scan_log import ScanLog

tracking_bp = Blueprint('tracking', __name__)

@tracking_bp.route('/track')
def track_home():
    q = request.args.get('q', '').strip()
    parcel = None
    scan_history = []
    progress = 0
    error = None
    
    if q:
        parcel = Parcel.query.filter(
            (Parcel.tracking_number == q.upper()) | (Parcel.courier_id == q)
        ).first()
        if parcel:
            scan_history = ScanLog.query.filter_by(parcel_id=parcel.id).order_by(ScanLog.timestamp.asc()).all()
            
            # Filter scans: if user is not superadmin, only show scans up to the first 'delivered' scan
            if not (current_user.is_authenticated and current_user.role == 'superadmin'):
                filtered_scans = []
                for scan in scan_history:
                    filtered_scans.append(scan)
                    if scan.action == 'delivered':
                        break
                scan_history = filtered_scans
                
            progress_map = {'pending': 10, 'in_transit': 50, 'delivered': 100, 'failed': 75, 'returned': 75}
            progress = progress_map.get(parcel.status, 0)
        else:
            error = f'No parcel found with tracking number: {q}'
    
    return render_template('tracking/track.html',
        parcel=parcel,
        scan_history=scan_history,
        progress=progress,
        tracking_number=q,
        error=error
    )

@tracking_bp.route('/track/<tracking_number>')
def track_parcel(tracking_number):
    from datetime import datetime, timedelta
    from app import db
    from app.models.branch import Branch
    from app.services.email_service import send_delivery_notification
    from flask import current_app
    
    parcel = Parcel.query.filter_by(tracking_number=tracking_number.upper()).first_or_404()
    
    # If user is logged in, process QR scan
    if current_user.is_authenticated:
        user_identifier = current_user.email if current_user.email else (current_user.username if current_user.username else current_user.name)
        display_emp_name = f"{current_user.name} ({user_identifier})" if (current_user.email and current_user.name != current_user.email) else user_identifier
        
        # Check if the user is the intended receiver
        is_intended_receiver = False
        if parcel.receiver_email and current_user.email:
            if current_user.email.strip().lower() == parcel.receiver_email.strip().lower():
                is_intended_receiver = True
        
        # Check if user recently scanned (within last 30 seconds) to avoid duplicates on refresh
        recent_log = ScanLog.query.filter_by(
            parcel_id=parcel.id,
            employee_id=current_user.id
        ).filter(ScanLog.timestamp >= datetime.utcnow() - timedelta(seconds=30)).first()
        
        if not recent_log:
            branch = db.session.get(Branch, current_user.branch_id) if current_user.branch_id else None
            branch_name = branch.name if branch else (current_user.branch_name or 'Web App')
            
            is_destination_branch = (parcel.receiver_branch_id and current_user.branch_id == parcel.receiver_branch_id)
            if (is_intended_receiver or is_destination_branch) and parcel.status != 'delivered':
                # Mark as delivered since destination branch or intended receiver scanned it!
                parcel.status = 'delivered'
                parcel.delivered_at = datetime.utcnow()
                parcel.is_archived = True
                parcel.archived_at = datetime.utcnow()
                
                notes = f"Parcel delivered at destination branch: {branch_name}"
                if is_intended_receiver:
                    notes = f"Parcel received & delivery verified by intended receiver {display_emp_name}"
                
                scan_log = ScanLog(
                    parcel_id=parcel.id,
                    tracking_number=parcel.tracking_number,
                    branch_id=current_user.branch_id,
                    branch_name=branch_name,
                    employee_id=current_user.id,
                    employee_name=display_emp_name,
                    action='delivered',
                    notes=notes,
                    timestamp=datetime.utcnow()
                )
                db.session.add(scan_log)
                db.session.commit()
                
                # Send delivery confirmation email to sender
                try:
                    send_delivery_notification(
                        parcel.sender_email, parcel.receiver_email,
                        parcel.tracking_number, parcel.receiver_name,
                        current_app.config['COMPANY_NAME'], current_app.config['BASE_URL']
                    )
                except Exception:
                    pass
            else:
                # Intermediate scan by another person or staff: status stays pending/in_transit
                action = 'qr_scanned'
                notes = f"QR Code scanned by {display_emp_name}"
                if parcel.status != 'delivered':
                    notes += " (Pending intended receiver scan)"
                    
                scan_log = ScanLog(
                    parcel_id=parcel.id,
                    tracking_number=parcel.tracking_number,
                    branch_id=current_user.branch_id,
                    branch_name=branch_name,
                    employee_id=current_user.id,
                    employee_name=display_emp_name,
                    action=action,
                    notes=notes,
                    timestamp=datetime.utcnow()
                )
                db.session.add(scan_log)
                db.session.commit()
    
    scan_history = ScanLog.query.filter_by(parcel_id=parcel.id).order_by(ScanLog.timestamp.asc()).all()
    
    # Filter scans: Non-admin users only see history up to the first 'delivered' scan
    # Admin sees FULL lifetime hierarchy (including scans after delivery when forwarded to others)
    if not (current_user.is_authenticated and current_user.role == 'superadmin'):
        filtered_scans = []
        for scan in scan_history:
            filtered_scans.append(scan)
            if scan.action == 'delivered':
                break
        scan_history = filtered_scans
        
    progress_map = {'pending': 10, 'in_transit': 50, 'delivered': 100, 'failed': 75, 'returned': 75}
    progress = progress_map.get(parcel.status, 0)
    return render_template('tracking/track.html',
        parcel=parcel,
        scan_history=scan_history,
        progress=progress,
        tracking_number=tracking_number
    )

@tracking_bp.route('/api/track/<tracking_number>')
def api_track(tracking_number):
    parcel = Parcel.query.filter_by(tracking_number=tracking_number.upper()).first()
    if not parcel:
        return jsonify({'success': False, 'message': 'Not found'}), 404
    
    scan_history = ScanLog.query.filter_by(parcel_id=parcel.id).order_by(ScanLog.timestamp.asc()).all()
    return jsonify({
        'success': True,
        'tracking_number': parcel.tracking_number,
        'status': parcel.status,
        'status_label': parcel.status_label,
        'sender': parcel.sender_name,
        'receiver': parcel.receiver_name,
        'dispatched_at': parcel.dispatched_at.isoformat() if parcel.dispatched_at else None,
        'delivered_at': parcel.delivered_at.isoformat() if parcel.delivered_at else None,
        'history': [{
            'action': s.action_label,
            'branch': s.branch_name,
            'employee': s.employee_name,
            'timestamp': s.timestamp.isoformat(),
            'notes': s.notes
        } for s in scan_history]
    })


@tracking_bp.route('/pushpak-track')
@login_required
def pushpak_track_page():
    """Dedicated Pushpak Courier Live Tracking page."""
    docket = request.args.get('docket', '').strip()
    return render_template('tracking/pushpak_track.html', docket=docket)

