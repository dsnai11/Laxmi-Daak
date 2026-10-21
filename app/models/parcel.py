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
    """Superadmin, the creator, or a user of the sender branch may modify a parcel."""
    if not user or not user.is_authenticated:
        return False
    if user.role == 'superadmin':
        return True
    if parcel.created_by == user.id:
        return True
    return bool(user.branch_id and user.branch_id == parcel.sender_branch_id)


def user_can_view_parcel(user, parcel):
    """True when the parcel falls inside the user's visibility scope."""
    if not user or not user.is_authenticated:
        return False
    cond = get_user_parcel_filter(user)
    if cond is None:
        return True
    if cond is False:
        return False
    return Parcel.query.filter(Parcel.id == parcel.id, cond).first() is not None


def get_user_parcel_filter(user):
    """
    Returns an SQLAlchemy filter condition for parcels visible to the given user.
    - Superadmin: None (unfiltered, sees all).
    - Branch manager (role == 'manager'):
        Parcels where their branch is sender, current, or receiver branch.
    - Department employee / regular user (role == 'employee'):
        Parcels where user is personally the SENDER (created_by, sender_email, sender_name)
        OR the RECEIVER (receiver_email, receiver_name).
    """
    from sqlalchemy import or_

    if not user or not user.is_authenticated:
        return False

    if user.role == 'superadmin':
        return None

    if user.role == 'manager' and user.branch_id:
        return or_(
            Parcel.sender_branch_id == user.branch_id,
            Parcel.current_branch_id == user.branch_id,
            Parcel.receiver_branch_id == user.branch_id
        )

    # Employee / personal user: strictly sender or receiver
    conditions = [Parcel.created_by == user.id]

    if user.email and '@' in user.email:
        em = user.email.strip()
        conditions.append(Parcel.sender_email.ilike(em))
        conditions.append(Parcel.receiver_email.ilike(em))

    if user.name and user.name.strip():
        nm = user.name.strip()
        conditions.append(Parcel.sender_name.ilike(nm))
        conditions.append(Parcel.receiver_name.ilike(nm))
        parts = nm.split()
        if len(parts) > 0 and len(parts[0]) >= 3:
            conditions.append(Parcel.sender_name.ilike(f"{parts[0]}%"))
            conditions.append(Parcel.receiver_name.ilike(f"{parts[0]}%"))

    if user.username and user.username.strip():
        un = user.username.strip()
        conditions.append(Parcel.sender_name.ilike(un))
        conditions.append(Parcel.receiver_name.ilike(un))

    return or_(*conditions)

