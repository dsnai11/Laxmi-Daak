from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.branch import Branch
from app.models.parcel import Parcel
from app.models.scan_log import ScanLog
from datetime import datetime, timedelta
from sqlalchemy import func
from functools import wraps
from flask import abort

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superadmin':
            abort(403)
        return f(*args, **kwargs)
    return decorated

def manager_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['superadmin', 'manager']:
            abort(403)
        return f(*args, **kwargs)
    return decorated

@dashboard_bp.route('/')
@login_required
def index():
    if current_user.role == 'superadmin':
        return redirect(url_for('dashboard.admin_dashboard'))
    elif current_user.role == 'manager':
        return redirect(url_for('dashboard.manager_dashboard'))
    return redirect(url_for('dashboard.employee_dashboard'))

@dashboard_bp.route('/admin')
@login_required
@superadmin_required
def admin_dashboard():
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import date
    today_date = date.today()
    
    overdue_count = Parcel.query.filter(
        Parcel.due_date != None,
        Parcel.due_date < today_date,
        Parcel.status.in_(['pending', 'in_transit'])
    ).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count()
    
    stats = {
        'total_parcels': Parcel.query.filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count(),
        'total_branches': Branch.query.filter_by(is_active=True).count(),
        'total_employees': User.query.filter(User.role.in_(['manager','employee']), User.is_active==True).count(),
        'pending': Parcel.query.filter_by(status='pending').filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count(),
        'in_transit': Parcel.query.filter_by(status='in_transit').filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count(),
        'delivered': Parcel.query.filter_by(status='delivered').filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count(),
        'failed': Parcel.query.filter_by(status='failed').filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count(),
        'delivered_today': Parcel.query.filter(Parcel.delivered_at >= today_start, Parcel.status=='delivered').filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count(),
        'overdue': overdue_count
    }
    
    recent_scans = ScanLog.query.order_by(ScanLog.timestamp.desc()).limit(15).all()
    
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
    
    chart = {'labels': labels, 'data': data}
    
    # Fetch branch stats correctly
    all_active_branches = Branch.query.filter_by(is_active=True).all()
    branch_stats = []
    for branch in all_active_branches:
        # Total parcels dispatched from this branch
        total_parcels = Parcel.query.filter_by(sender_branch_id=branch.id).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count()
        if total_parcels > 0:
            delivered_parcels = Parcel.query.filter_by(sender_branch_id=branch.id, status='delivered').filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count()
            rate = round((delivered_parcels / total_parcels) * 100, 1)
            branch_stats.append({
                'name': branch.name,
                'total': total_parcels,
                'delivered': delivered_parcels,
                'rate': rate
            })
    # Sort by total parcels descending, limit to top 10
    branch_stats = sorted(branch_stats, key=lambda x: x['total'], reverse=True)[:10]
    
    return render_template('dashboard/admin.html', stats=stats, recent_scans=recent_scans, chart=chart, branch_stats=branch_stats)

@dashboard_bp.route('/manager')
@login_required
@manager_required
def manager_dashboard():
    branch_id = current_user.branch_id
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import date
    today_date = date.today()
    
    branch_total = 0
    pending = 0
    dispatched_today = 0
    delivered_today = 0
    overdue = 0
    employees = []
    recent_scans = []
    pending_deliveries = []

    if branch_id:
        branch_total = Parcel.query.filter(
            (Parcel.sender_branch_id==branch_id) | 
            (Parcel.current_branch_id==branch_id) | 
            (Parcel.receiver_branch_id==branch_id)
        ).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count()
        pending = Parcel.query.filter(
            ((Parcel.current_branch_id == branch_id) | (Parcel.receiver_branch_id == branch_id)),
            Parcel.status.in_(['pending', 'in_transit'])
        ).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count()
        dispatched_today = Parcel.query.filter(Parcel.dispatched_at >= today_start, Parcel.sender_branch_id==branch_id).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count()
        delivered_today = Parcel.query.filter(Parcel.delivered_at >= today_start, Parcel.status=='delivered', Parcel.current_branch_id==branch_id).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count()
        overdue = Parcel.query.filter(
            Parcel.due_date != None,
            Parcel.due_date < today_date,
            Parcel.status.in_(['pending', 'in_transit']),
            (Parcel.sender_branch_id==branch_id) | (Parcel.current_branch_id==branch_id) | (Parcel.receiver_branch_id==branch_id)
        ).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count()
        
        employees_raw = User.query.filter_by(branch_id=branch_id, is_active=True).all()
        for emp in employees_raw:
            emp_scans_today = ScanLog.query.filter(
                ScanLog.employee_id == emp.id,
                ScanLog.timestamp >= today_start
            ).count()
            emp_scans_total = ScanLog.query.filter_by(employee_id=emp.id).count()
            
            employees.append({
                'name': emp.name,
                'today_scans': emp_scans_today,
                'total_handled': emp_scans_total,
                'active': emp.is_active
            })
            
        recent_scans_raw = ScanLog.query.filter_by(branch_id=branch_id).order_by(ScanLog.timestamp.desc()).limit(15).all()
        recent_scans = [
            {
                'time': s.timestamp.strftime('%I:%M %p'),
                'tracking_no': s.tracking_number,
                'action': s.action_label
            } for s in recent_scans_raw
        ]
        
        pending_parcels = Parcel.query.filter(
            ((Parcel.current_branch_id==branch_id) | (Parcel.receiver_branch_id==branch_id)),
            Parcel.status.in_(['pending','in_transit'])
        ).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).order_by(Parcel.priority.desc(), Parcel.dispatched_at).limit(10).all()
        
        pending_deliveries = [
            {
                'tracking_no': p.tracking_number,
                'receiver_name': p.receiver_name,
                'priority': p.priority.title()
            } for p in pending_parcels
        ]
        
    stats = {
        'files_in_branch': branch_total,
        'pending': pending,
        'dispatched_today': dispatched_today,
        'delivered_today': delivered_today,
        'overdue': overdue
    }
    
    return render_template('dashboard/manager.html', 
                           stats=stats, 
                           employees=employees, 
                           recent_scans=recent_scans, 
                           pending_deliveries=pending_deliveries)

@dashboard_bp.route('/employee')
@login_required
def employee_dashboard():
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    # Only count real physical scan actions — exclude 'dispatched' and 'edited'
    # which are auto-created when a parcel is created/edited, not manually scanned
    REAL_SCAN_ACTIONS = ('received', 'out_for_delivery', 'delivered', 'failed',
                         'returned', 'qr_scanned', 'picked_up', 'delivered_pending', 'closed')
    today_scans_all = ScanLog.query.filter(
        ScanLog.employee_id==current_user.id,
        ScanLog.timestamp >= today_start
    ).order_by(ScanLog.timestamp.desc()).all()

    today_scans = [s for s in today_scans_all if s.action in REAL_SCAN_ACTIONS]
    today_count = len(today_scans)
    today_deliveries = sum(1 for s in today_scans if s.action == 'delivered')
    
    from datetime import date
    from sqlalchemy import or_
    today_date = date.today()

    # Strictly personal parcel condition for employee
    emp_personal_cond = [Parcel.created_by == current_user.id]
    if current_user.email and '@' in current_user.email:
        em = current_user.email.strip()
        emp_personal_cond.append(Parcel.receiver_email.ilike(em))
        emp_personal_cond.append(Parcel.sender_email.ilike(em))
    if current_user.name and current_user.name.strip():
        nm = current_user.name.strip()
        emp_personal_cond.append(Parcel.receiver_name.ilike(nm))
        emp_personal_cond.append(Parcel.sender_name.ilike(nm))
        parts = nm.split()
        if len(parts) > 0 and len(parts[0]) >= 3:
            emp_personal_cond.append(Parcel.receiver_name.ilike(f"{parts[0]}%"))
            emp_personal_cond.append(Parcel.sender_name.ilike(f"{parts[0]}%"))
    if current_user.username and current_user.username.strip():
        un = current_user.username.strip()
        emp_personal_cond.append(Parcel.receiver_name.ilike(un))
        emp_personal_cond.append(Parcel.sender_name.ilike(un))

    # If user is a branch employee with NO department (working at a specific branch):
    if current_user.branch_id and not current_user.department_id:
        pending_filter = or_(
            Parcel.current_branch_id == current_user.branch_id,
            Parcel.receiver_branch_id == current_user.branch_id,
            *emp_personal_cond
        )
    else:
        # Department employee: strictly personal (never leaks branch or other department parcels)
        pending_filter = or_(*emp_personal_cond)

    pending_count = Parcel.query.filter(
        pending_filter,
        Parcel.status.in_(['pending', 'in_transit', 'picked_up', 'query_raised'])
    ).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count()

    pending_query = Parcel.query.filter(
        pending_filter,
        Parcel.status.in_(['pending', 'in_transit', 'picked_up', 'query_raised'])
    ).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).order_by(Parcel.dispatched_at.desc()).limit(15).all()

    # Overdue count: strictly personal sender or receiver for employee
    overdue_count = Parcel.query.filter(
        Parcel.due_date != None,
        Parcel.due_date < today_date,
        Parcel.status.in_(['pending', 'in_transit']),
        or_(*emp_personal_cond)
    ).filter((Parcel.is_archived == False) | (Parcel.is_archived == None)).count()

    stats = {
        'scans_today': today_count,
        'deliveries_today': today_deliveries,
        'pending_branch': pending_count,
        'overdue': overdue_count
    }
    
    recent_scans = [
        {
            'time': s.timestamp.strftime('%I:%M %p'),
            'tracking_no': s.tracking_number,
            'action': s.action_label
        } for s in today_scans[:15]
    ]
    
    pending_files = [
        {
            'tracking_no': p.tracking_number,
            'receiver_name': p.receiver_name
        } for p in pending_query
    ]
    
    return render_template('dashboard/employee.html', 
                           stats=stats, 
                           recent_scans=recent_scans, 
                           pending_files=pending_files)

