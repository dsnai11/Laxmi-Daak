from app import db
from datetime import datetime

class StateBillingRate(db.Model):
    __tablename__ = 'state_billing_rates'
    
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(50), nullable=False, default='Default')
    courier_name = db.Column(db.String(50), nullable=False) # e.g. 'Blue Dart', 'Pushpak', etc.
    base_rate = db.Column(db.Float, default=0.0)
    per_kg_rate = db.Column(db.Float, default=0.0)
    
    # Pushpak-specific gram-based tiered pricing
    pushpak_normal_base  = db.Column(db.Float, default=35.0)   # ₹35 for first 500g
    pushpak_normal_extra = db.Column(db.Float, default=25.0)   # ₹25 per extra 500g
    pushpak_premium_base  = db.Column(db.Float, default=300.0) # ₹300 for first 500g
    pushpak_premium_extra = db.Column(db.Float, default=200.0) # ₹200 per extra 500g
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'state': self.state,
            'courier_name': self.courier_name,
            'base_rate': self.base_rate,
            'per_kg_rate': self.per_kg_rate,
            'pushpak_normal_base': self.pushpak_normal_base,
            'pushpak_normal_extra': self.pushpak_normal_extra,
            'pushpak_premium_base': self.pushpak_premium_base,
            'pushpak_premium_extra': self.pushpak_premium_extra,
        }
