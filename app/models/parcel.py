import random
import json
from datetime import datetime
from app import db

STATUS_LABELS = {
    'query_raised': 'Query Raised (Pending Pickup)',
    'picked_up': 'Picked Up & Dispatched',
    'pending': 'Pending',
    'in_transit': 'In Transit',
    'delivered_pending': 'Delivered (Pending Sender Confirmation)',
    'delivered': 'Delivered & Confirmed',
    'failed': 'Failed',
    'returned': 'Returned',
    'closed': 'Closed & Confirmed'
}

PRIORITY_LABELS = {
    'normal': 'Normal',
    'urgent': 'Urgent',
    'express': 'Express'
}

TRANSFER_MODE_LABELS = {
    'by_hand': 'By Hand',
    'by_bus': 'By Bus',
    'by_courier': 'By Courier'
}

class Parcel(db.Model):
    __tablename__ = 'parcels'
    
    id = db.Column(db.Integer, primary_key=True)
    tracking_number = db.Column(db.String(30), unique=True, nullable=False)
    qr_code_path = db.Column(db.String(200), default='')
    
    # Sender info
    sender_name = db.Column(db.String(100), nullable=False)
    sender_phone = db.Column(db.String(20), default='')
    sender_email = db.Column(db.String(120), default='')
    sender_address = db.Column(db.Text, default='')
    sender_branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    sender_department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    sender_department_name = db.Column(db.String(100), default='')
    
    # Receiver info
    receiver_name = db.Column(db.String(100), nullable=False)
    receiver_phone = db.Column(db.String(20), default='')
    receiver_email = db.Column(db.String(120), default='')
    receiver_address = db.Column(db.Text, default='')
    receiver_branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    receiver_department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    receiver_department_name = db.Column(db.String(100), default='')
    
    # Package details
    description = db.Column(db.Text, default='')
    priority = db.Column(db.String(20), default='normal')
    weight = db.Column(db.Float, default=0.0)
    transfer_mode = db.Column(db.String(20), default='by_courier')   # by_hand, by_bus, by_courier
    courier_partner = db.Column(db.String(50), default='')           # blue dart, pushpak, professional, trackon
    courier_id = db.Column(db.String(100), default='')               # Courier company's own docket / AWB number
    
    # Custom transfer mode details
    bus_number = db.Column(db.String(50), default='')
    driver_phone = db.Column(db.String(30), default='')
    hand_carry_name = db.Column(db.String(100), default='')
    hand_carry_phone = db.Column(db.String(30), default='')
    
    billing_amount = db.Column(db.Float, default=0.0)
    
    special_instructions = db.Column(db.Text, default='')
    _photos = db.Column('photos', db.Text, default='[]')             # JSON list
    
    # Status & tracking
    status = db.Column(db.String(20), default='pending')
    current_branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    assigned_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    receiver_branch_name = db.Column(db.String(100), default='')
    dispatched_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.Date, nullable=True)                     # Expected delivery date
    delivered_at = db.Column(db.DateTime, nullable=True)
    overdue_email_sent = db.Column(db.Boolean, default=False, server_default='0')
    last_overdue_email_sent = db.Column(db.Date, nullable=True)
    is_archived = db.Column(db.Boolean, default=False, server_default='0') # Archive flag
    archived_at = db.Column(db.DateTime, nullable=True)             # When archived
    missing_fields_email_sent = db.Column(db.Boolean, default=False, server_default='0') # Missing fields reminder sent flag

    # Pushpak API Integration Fields (ADD-ON)
    pushpak_doc_no = db.Column(db.String(50), default='')           # Pushpak's own Doc_No from booking API
    pushpak_booking_status = db.Column(db.String(20), default='')   # 'booked', 'pickup_requested', 'failed'
    pushpak_booked_at = db.Column(db.DateTime, nullable=True)       # When booked via Pushpak API
    
    # Relationships
    current_branch = db.relationship('Branch', foreign_keys=[current_branch_id], backref='current_parcels')
    creator = db.relationship('User', foreign_keys=[created_by])
    assigned_admin = db.relationship('User', foreign_keys=[assigned_admin_id])
    sender_department = db.relationship('Department', foreign_keys=[sender_department_id])
    receiver_department = db.relationship('Department', foreign_keys=[receiver_department_id])
    scan_logs = db.relationship('ScanLog', backref='parcel', lazy='dynamic', order_by='ScanLog.timestamp')
    
    @property
    def photos(self):
        try:
            return json.loads(self._photos or '[]')
        except:
            return []
    
    @photos.setter
    def photos(self, value):
        self._photos = json.dumps(value)
    
    @property
    def is_overdue(self):
        """True when due_date has passed and parcel is not yet delivered."""
        if not self.due_date:
            return False
        if self.status in ('delivered', 'delivered_pending', 'closed', 'returned'):
            return False
        from datetime import date
        return date.today() > self.due_date
    
    @property
    def status_label(self):
        return STATUS_LABELS.get(self.status, self.status)
    
    @property
    def priority_label(self):
        return PRIORITY_LABELS.get(self.priority, self.priority)
        
    @property
    def transfer_mode_label(self):
        return TRANSFER_MODE_LABELS.get(self.transfer_mode, 'By Courier')
    
    def __repr__(self):
        return f'<Parcel {self.tracking_number} [{self.status}]>'


def generate_tracking_number():
    now = datetime.utcnow()
    rand_part = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
    return f'CRR-{now.year}-{rand_part}'


def user_can_manage_parcel(user, parcel):
    """Only the superadmin or the person who created the parcel may change or delete it."""
    if not user or not user.is_authenticated:
        return False
    return user.role == 'superadmin' or parcel.created_by == user.id


def user_can_view_parcel(user, parcel):
    """True when the parcel falls inside the user's visibility scope."""
    if not user or not user.is_authenticated:
        return False
    cond = get_user_parcel_filter(user)
    if cond is None:
        return True
    if cond is False:
        return False
    # Department users may also open parcels raised by or addressed to their own department
    if user.role == 'employee' and user.department_id and user.department_id in (
            parcel.sender_department_id, parcel.receiver_department_id):
        return True
    return Parcel.query.filter(Parcel.id == parcel.id, cond).first() is not None


# Scan actions that mean "this person physically had the parcel in their hands"
HANDLING_ACTIONS = ('received', 'out_for_delivery', 'delivered', 'failed', 'returned')


def _personal_conditions(user):
    """Parcels that belong to this person.

    - sent by them: created by their login (nothing else counts as "sent by")
    - sent to them: their e-mail or their exact name is the receiver
    Exact (case-insensitive) matches only. The sender name and sender e-mail are
    deliberately not matched: they are prefilled with the branch name / a shared mailbox
    ("JAIPUR HO", courier@lifc.in), which made every login sharing them see every parcel
    that branch sent. No first-name prefix matching either.
    """
    from sqlalchemy import func

    conditions = [Parcel.created_by == user.id]

    if user.email and '@' in user.email:
        conditions.append(func.lower(Parcel.receiver_email) == user.email.strip().lower())

    for value in (user.name, user.username):
        if value and len(value.strip()) > 2:
            conditions.append(func.lower(Parcel.receiver_name) == value.strip().lower())

    return conditions


def branch_is_shared(branch_id):
    """True when several people log in for the same branch (e.g. Jaipur HO).

    A branch with a single login is that login's only user, so everything addressed
    to / held at the branch belongs to it. In a shared branch that would show one
    person's parcels to everybody else, so only personal matches count there.
    """
    from app.models.user import User

    if not branch_id:
        return False
    return User.query.filter(
        User.branch_id == branch_id,
        User.is_active == True,  # noqa: E712
        User.role != 'superadmin',
    ).count() > 1


def get_user_parcel_filter(user):
    """
    Returns an SQLAlchemy filter condition for parcels visible to the given user.
    - Superadmin: None (unfiltered, sees all).
    - Everybody else sees the parcels they sent, that are addressed to them, or that they
      physically handled (scanned as received / out for delivery / delivered / failed / returned).
    - Department users also see parcels addressed to their department.
    - A DO (role == 'manager') who is the only login of their branch also sees every parcel
      sent from, addressed to, or held at that branch (even if another login, e.g. the admin,
      created it for the branch).
    - False when nobody is logged in.
    """
    from sqlalchemy import and_, or_, select
    from app.models.scan_log import ScanLog

    if not user or not user.is_authenticated:
        return False

    if user.role == 'superadmin':
        return None

    conditions = _personal_conditions(user)

    # Parcels this person physically handled. The 'qr_scanned' / 'edited' / 'dispatched'
    # log entries are deliberately excluded: merely opening a tracking link must not grant access.
    conditions.append(Parcel.id.in_(
        select(ScanLog.parcel_id).where(
            ScanLog.employee_id == user.id,
            ScanLog.action.in_(HANDLING_ACTIONS),
        )
    ))

    if user.role == 'employee' and user.department_id:
        conditions.append(Parcel.receiver_department_id == user.department_id)

    if user.role == 'manager' and user.branch_id and not branch_is_shared(user.branch_id):
        conditions.append(Parcel.sender_branch_id == user.branch_id)
        conditions.append(Parcel.receiver_branch_id == user.branch_id)
        conditions.append(and_(
            Parcel.current_branch_id == user.branch_id,
            or_(Parcel.sender_branch_id.is_(None), Parcel.sender_branch_id != user.branch_id),
        ))

    return or_(*conditions)
