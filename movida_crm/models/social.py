from datetime import datetime
from extensions import db

class SocialNumber(db.Model):
    __tablename__ = 'social_numbers'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    platform = db.Column(db.String(30), nullable=False)  # Facebook, Instagram, TikTok, WhatsApp, Other
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.now)
    is_sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    converted_to_customer = db.Column(db.Boolean, default=False)

    assignments = db.relationship('SocialAssignment', backref='social_number', lazy='dynamic')

    def get_platform_display(self):
        platforms = {'Facebook': 'فيسبوك', 'Instagram': 'انستقرام', 'TikTok': 'تيك توك', 'WhatsApp': 'واتساب', 'Other': 'أخرى'}
        return platforms.get(self.platform, self.platform)


class SocialAssignment(db.Model):
    __tablename__ = 'social_assignments'

    id = db.Column(db.Integer, primary_key=True)
    social_number_id = db.Column(db.Integer, db.ForeignKey('social_numbers.id'), nullable=False)
    sales_employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.now)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    sales_employee = db.relationship('User', foreign_keys=[sales_employee_id], backref='received_numbers')
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_id])
