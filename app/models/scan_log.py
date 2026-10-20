from datetime import datetime
from app import db

ACTION_LABELS = {
    'dispatched': 'Dispatched',
    'received': 'Received at Branch',
    'out_for_delivery': 'Out for Delivery',
    'delivered': 'Delivered',
    'failed': 'Delivery Failed',
    'returned': 'Returned',
    'qr_scanned': 'QR Scanned',
    'edited': 'Details Updated',
    # Dispatch Query Workflow
    'query_raised': 'Dispatch Query Raised',
    'picked_up': 'Picked Up & Dispatched by Admin',
    'delivered_pending': 'Delivered (Awaiting Sender Confirmation)',
    'closed': 'Query Closed & Confirmed by Sender',
}

ACTION_ICONS = {
    'dispatched': '📦',
    'received': '🏢',
    'out_for_delivery': '🚚',
    'delivered': '✅',
    'failed': '❌',
    'returned': '↩️',
    'qr_scanned': '🔍',
    'edited': '✏️',
    # Dispatch Query Workflow
    'query_raised': '📬',
    'picked_up': '🚚',
    'delivered_pending': '📦',
    'closed': '🔒',
}

class ScanLog(db.Model):
    __tablename__ = 'scan_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    parcel_id = db.Column(db.Integer, db.ForeignKey('parcels.id'), nullable=False)
    tracking_number = db.Column(db.String(30), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    branch_name = db.Column(db.String(100), default='')
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    employee_name = db.Column(db.String(100), default='')
    action = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.Text, default='')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    branch = db.relationship('Branch', foreign_keys=[branch_id])
    employee = db.relationship('User', foreign_keys=[employee_id])
    
    @property
    def action_label(self):
        return ACTION_LABELS.get(self.action, self.action)
    
    @property
    def action_icon(self):
        return ACTION_ICONS.get(self.action, '📍')
    
    def __repr__(self):
        return f'<ScanLog {self.tracking_number} - {self.action} at {self.timestamp}>'
