from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, sales, social, files
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    social_numbers = db.relationship('SocialNumber', backref='employee', lazy='dynamic', foreign_keys='SocialNumber.employee_id')
    customers = db.relationship('Customer', backref='sales_employee', lazy='dynamic', foreign_keys='Customer.sales_employee_id')
    logs = db.relationship('ActivityLog', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_role_display(self):
        roles = {'admin': 'مدير', 'sales': 'موظف مبيعات', 'social': 'موظف سوشيال ميديا', 'files': 'موظف ملفات'}
        return roles.get(self.role, self.role)

    def __repr__(self):
        return f'<User {self.username}>'
