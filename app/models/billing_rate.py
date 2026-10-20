from app import db
from datetime import datetime

class BillingRate(db.Model):
    __tablename__ = 'billing_rates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False) # 'Blue Dart', 'Pushpak', 'Professional', 'Trackon', 'Other Company', 'By Bus', 'By Hand'
    base_rate = db.Column(db.Float, default=0.0)
    per_kg_rate = db.Column(db.Float, default=0.0)
    
    # State-wise billing rates
    intra_state_base_rate = db.Column(db.Float, default=0.0)
    intra_state_per_kg_rate = db.Column(db.Float, default=0.0)
    inter_state_base_rate = db.Column(db.Float, default=0.0)
    inter_state_per_kg_rate = db.Column(db.Float, default=0.0)
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'name': self.name,
            'base_rate': self.base_rate,
            'per_kg_rate': self.per_kg_rate,
            'intra_state_base_rate': self.intra_state_base_rate,
            'intra_state_per_kg_rate': self.intra_state_per_kg_rate,
            'inter_state_base_rate': self.inter_state_base_rate,
            'inter_state_per_kg_rate': self.inter_state_per_kg_rate
        }
