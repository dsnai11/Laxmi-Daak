from datetime import datetime
from app import db

class SecurityLog(db.Model):
    __tablename__ = 'security_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username = db.Column(db.String(100), default='system')
    action = db.Column(db.String(100), nullable=False) # login_success, login_failed, logout, dispatch_created, parcel_edited, parcel_deleted, parcel_archived, bulk_upload, scan_recorded
    ip_address = db.Column(db.String(50), default='')
    user_agent = db.Column(db.String(255), default='')
    details = db.Column(db.Text, default='')
    
    # Relationship
    user = db.relationship('User', foreign_keys=[user_id])
    
    def __repr__(self):
        return f'<SecurityLog {self.action} by {self.username} at {self.timestamp}>'


def log_security_action(action, details, user_id=None, username='system'):
    from app import db
    from flask import request
    
    ip_addr = 'unknown'
    user_agt = 'unknown'
    try:
        ip_addr = request.remote_addr or 'unknown'
        user_agt = request.headers.get('User-Agent', 'unknown')
    except RuntimeError:
        pass
        
    log_entry = SecurityLog(
        action=action,
        details=details,
        user_id=user_id,
        username=username,
        ip_address=ip_addr,
        user_agent=user_agt
    )
    db.session.add(log_entry)
    db.session.commit()

