from datetime import datetime
from extensions import db

class Interview(db.Model):
    __tablename__ = 'interviews'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    interview_date = db.Column(db.DateTime, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='active')  # active, cancelled
    # For files module interviews
    client_phone = db.Column(db.String(20), nullable=True)
    client_name = db.Column(db.String(120), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    sales_employee_name = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    employee = db.relationship('User', foreign_keys=[employee_id])
