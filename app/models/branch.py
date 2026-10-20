from app import db
from datetime import datetime

class Branch(db.Model):
    __tablename__ = 'branches'
    
    id = db.Column(db.Integer, primary_key=True)
    branch_code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(50), default='')
    state = db.Column(db.String(50), default='')
    address = db.Column(db.Text, default='')
    phone = db.Column(db.String(20), default='')
    pincode = db.Column(db.String(10), default='')
    email = db.Column(db.String(120), default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    sent_parcels = db.relationship('Parcel', foreign_keys='Parcel.sender_branch_id', backref='sender_branch', lazy='dynamic')
    received_parcels = db.relationship('Parcel', foreign_keys='Parcel.receiver_branch_id', backref='receiver_branch', lazy='dynamic')
    
    @property
    def employee_count(self):
        from app.models.user import User
        return User.query.filter_by(branch_id=self.id, is_active=True).count()
    
    def __repr__(self):
        return f'<Branch {self.branch_code} - {self.name}>'
