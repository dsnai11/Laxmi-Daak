from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db
from app.models.parcel import Parcel, get_user_parcel_filter, user_can_manage_parcel
from app.models.branch import Branch
from app.models.scan_log import ScanLog
from app.models.user import User
from datetime import datetime, timedelta
from sqlalchemy import func

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/dashboard/stats')
@login_required
def dashboard_stats():
    stats = {
        'total_parcels': Parcel.query.filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count(),
        'total_branches': Branch.query.filter_by(is_active=True).count(),
        'total_employees': User.query.filter(User.role.in_(['manager','employee']), User.is_active==True).count(),
        'pending': Parcel.query.filter_by(status='pending').filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count(),
        'in_transit': Parcel.query.filter_by(status='in_transit').filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count(),
        'delivered': Parcel.query.filter_by(status='delivered').filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count(),
        'failed': Parcel.query.filter_by(status='failed').filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count(),
    }
    return jsonify(stats)

@api_bp.route('/dashboard/chart-data')
@login_required
def chart_data():
    labels = []
    data = []
    today = datetime.utcnow().date()
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start = datetime(day.year, day.month, day.day)
        day_end = datetime(day.year, day.month, day.day, 23, 59, 59)
        count = Parcel.query.filter(Parcel.dispatched_at.between(day_start, day_end)).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count()
        labels.append(day.strftime('%a %d'))
        data.append(count)
    return jsonify({'labels': labels, 'data': data})

@api_bp.route('/branches')
@login_required
def get_branches():
    branches = Branch.query.filter_by(is_active=True).order_by(Branch.name).all()
    return jsonify([{'id': b.id, 'branch_code': b.branch_code, 'name': b.name, 'city': b.city, 'state': b.state} for b in branches])

@api_bp.route('/parcels/search')
@login_required
def search_parcels():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify([])
    query = Parcel.query.filter(
        (Parcel.tracking_number.ilike(f'%{q}%')) |
        (Parcel.sender_name.ilike(f'%{q}%')) |
        (Parcel.receiver_name.ilike(f'%{q}%'))
    )
    scope = get_user_parcel_filter(current_user)
    if scope is False:
        return jsonify([])
    if scope is not None:
        query = query.filter(scope)
    parcels = query.limit(10).all()
    return jsonify([{
        'tracking_number': p.tracking_number,
        'sender_name': p.sender_name,
        'receiver_name': p.receiver_name,
        'status': p.status_label
    } for p in parcels])

@api_bp.route('/stats/branch/<int:branch_id>')
@login_required
def branch_stats(branch_id):
    branch = db.session.get(Branch, branch_id)
    if not branch:
        return jsonify({'error': 'Branch not found'}), 404
    return jsonify({
        'name': branch.name,
        'total': Parcel.query.filter_by(sender_branch_id=branch_id).count(),
        'pending': Parcel.query.filter_by(current_branch_id=branch_id, status='pending').count(),
        'delivered': Parcel.query.filter_by(sender_branch_id=branch_id, status='delivered').count()
    })

@api_bp.route('/scan', methods=['POST'])
@login_required
def api_scan():
    """API endpoint for USB scanner integration."""
    from app.routes.scan import process_scan
    return process_scan()

@api_bp.route('/users/lookup')
@login_required
def lookup_user():
    # Only people who create dispatches/queries need to look up receivers
    if current_user.role not in ('superadmin', 'manager') and not (
        current_user.has_permission('can_new_dispatch') or
        current_user.has_permission('can_bulk_dispatch') or
        current_user.has_permission('can_raise_query')
    ):
        return jsonify({'success': False, 'message': 'Not authorized'}), 403

    email = request.args.get('email', '').strip().lower()
    if not email:
        return jsonify({'success': False, 'message': 'No email provided'}), 400

    # Exact (case-insensitive) match only; ilike would treat % and _ as wildcards
    user = User.query.filter(
        User.is_active == True,
        (func.lower(User.email) == email) | (func.lower(User.username) == email)
    ).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    # Get branch address if branch exists
    address = ""
    if user.branch_id:
        branch = db.session.get(Branch, user.branch_id)
        if branch:
            address_parts = [branch.address]
            if branch.city:
                address_parts.append(branch.city)
            if branch.state:
                address_parts.append(branch.state)
            if branch.pincode:
                address_parts.append(f"- {branch.pincode}")
            address = ", ".join([p for p in address_parts if p])
            
    return jsonify({
        'success': True,
        'name': user.name,
        'phone': user.phone,
        'email': user.email or user.username,
        'branch_id': user.branch_id,
        'address': address
    })

@api_bp.route('/billing/rates')
@login_required
def get_billing_rates():
    from app.models.state_billing_rate import StateBillingRate
    from app.utils import normalize_state_name
    
    raw_state = request.args.get('state', 'Default')
    state = normalize_state_name(raw_state)
    if not state or state.lower() == 'default':
        state = 'Default'
    
    # Try exact normalized state first
    rates = StateBillingRate.query.filter_by(state=state).all()
    
    # If still empty and not Default, try case-insensitive match
    if not rates and state != 'Default':
        from sqlalchemy import func
        rates = StateBillingRate.query.filter(
            func.lower(StateBillingRate.state) == state.lower()
        ).all()
    
    # Final fallback to Default
    if not rates and state != 'Default':
        rates = StateBillingRate.query.filter_by(state='Default').all()
        
    return jsonify({r.courier_name: r.to_dict() for r in rates})


# ========== PUSHPAK COURIER API INTEGRATION (ADD-ON) ==========

@api_bp.route('/pushpak/track/<docket_no>')
def pushpak_track_api(docket_no):
    """Fetch live tracking data from Pushpak Courier API.

    Stays public because the customer tracking page uses it, but only for
    dockets that belong to a parcel in our system (not an open proxy).
    """
    from app.services.pushpak_service import pushpak_track_delivery
    known = Parcel.query.filter(
        (Parcel.courier_id == docket_no) | (Parcel.pushpak_doc_no == docket_no)
    ).first()
    if not known:
        return jsonify({'success': False, 'message': 'Docket not found.'}), 404
    result = pushpak_track_delivery(docket_no)
    return jsonify(result)


@api_bp.route('/pushpak/pincode/<pincode>')
@login_required
def pushpak_pincode_api(pincode):
    """Search pincode via Pushpak Courier API."""
    from app.services.pushpak_service import pushpak_search_pincode
    result = pushpak_search_pincode(pincode)
    return jsonify(result)


@api_bp.route('/pushpak/book/<int:parcel_id>', methods=['POST'])
@login_required
def pushpak_book_api(parcel_id):
    """Book a parcel with Pushpak Courier API (Manual button trigger)."""
    from app.services.pushpak_service import pushpak_booking_request
    from app.models.parcel import Parcel
    from datetime import datetime
    
    parcel = db.session.get(Parcel, parcel_id)
    if not parcel:
        return jsonify({'success': False, 'message': 'Parcel not found.'}), 404
    if not user_can_manage_parcel(current_user, parcel):
        return jsonify({'success': False, 'message': 'Not authorized for this parcel.'}), 403

    # Check if already booked
    if parcel.pushpak_booking_status == 'booked':
        return jsonify({'success': False, 'message': f'Already booked with Pushpak. Doc No: {parcel.pushpak_doc_no}'})
    
    result = pushpak_booking_request(parcel)
    
    if result['success']:
        parcel.pushpak_doc_no = result.get('doc_no', '')
        parcel.pushpak_booking_status = 'booked'
        parcel.pushpak_booked_at = datetime.utcnow()
        # Also update courier_id if not already set
        if not parcel.courier_id and result.get('doc_no'):
            parcel.courier_id = result['doc_no']
        db.session.commit()
    
    return jsonify(result)


@api_bp.route('/pushpak/pickup/<int:parcel_id>', methods=['POST'])
@login_required
def pushpak_pickup_api(parcel_id):
    """Request pickup from Pushpak Courier API."""
    from app.services.pushpak_service import pushpak_pickup_request
    from app.models.parcel import Parcel
    from datetime import datetime
    
    parcel = db.session.get(Parcel, parcel_id)
    if not parcel:
        return jsonify({'success': False, 'message': 'Parcel not found.'}), 404
    if not user_can_manage_parcel(current_user, parcel):
        return jsonify({'success': False, 'message': 'Not authorized for this parcel.'}), 403

    result = pushpak_pickup_request(parcel)
    
    if result['success']:
        if parcel.pushpak_booking_status != 'booked':
            parcel.pushpak_booking_status = 'pickup_requested'
        if not parcel.pushpak_booked_at:
            parcel.pushpak_booked_at = datetime.utcnow()
        db.session.commit()
    
    return jsonify(result)
