from flask_login import UserMixin
from app import db
from datetime import datetime
import bcrypt
import json

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.LargeBinary, nullable=False)
    password_plain = db.Column(db.String(100), nullable=True) # Plain text password for admin lookup
    role = db.Column(db.String(20), default='employee')  # superadmin, manager, employee
    branch_id = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    branch_name = db.Column(db.String(100), default='')
    branch_code = db.Column(db.String(20), default='')
    email = db.Column(db.String(120), default='')
    phone = db.Column(db.String(20), default='')
    is_active = db.Column(db.Boolean, default=True)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    department_name = db.Column(db.String(100), default='')
    permissions = db.Column(db.Text, default='{}')  # Store permissions as JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    branch = db.relationship('Branch', backref=db.backref('members', lazy='dynamic'), foreign_keys=[branch_id])
    
    def is_superadmin(self):
        return self.role == 'superadmin'
    
    def is_manager(self):
        return self.role == 'manager'
    
    def is_employee(self):
        return self.role == 'employee'
        
    @property
    def role_display(self):
        if self.role == 'superadmin':
            return 'Admin'
        elif self.role == 'manager':
            return 'Branch Manager'
        elif self.role == 'employee':
            return 'Department'
        return self.role.title()
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        self.password_plain = None  # legacy column, never store plain text
    
    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash)

    def get_permissions(self):
        try:
            return json.loads(self.permissions or '{}')
        except Exception:
            return {}

    def has_permission(self, key):
        if self.is_superadmin():
            return True
        perms = self.get_permissions()
        if key in perms:
            return bool(perms[key])
        # Default permissions: operational features are enabled by default unless explicitly disabled
        default_denied = ['admin_settings', 'manage_users']
        if key in default_denied:
            return False
        # Department employees: dispatch features are OFF by default
        # Admin must explicitly grant them via the permissions panel
        if self.department_id and key in ('can_new_dispatch', 'can_bulk_dispatch'):
            return False
        return True

    def get_permissions_string(self):
        perms = self.get_permissions()
        return ",".join([k for k, v in perms.items() if v])

    def set_permissions(self, perms_dict):
        self.permissions = json.dumps(perms_dict)
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
