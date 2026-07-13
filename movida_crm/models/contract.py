from datetime import datetime
from extensions import db

class Contract(db.Model):
    __tablename__ = 'contracts'

    id = db.Column(db.Integer, primary_key=True)
    file_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    client_phone = db.Column(db.String(20), nullable=False, index=True)
    client_name = db.Column(db.String(120), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    total_cost = db.Column(db.Float, nullable=False, default=0)
    num_payments = db.Column(db.Integer, nullable=False, default=1)
    fingerprint_location = db.Column(db.String(200), nullable=True)
    fingerprint_date = db.Column(db.DateTime, nullable=True)
    sales_employee_name = db.Column(db.String(120), nullable=True)
    files_employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), default='active')  # active, closed
    visa_status = db.Column(db.String(30), default='under_review')  # under_review, accepted, rejected
    visa_image = db.Column(db.String(255), nullable=True)
    rejection_file = db.Column(db.String(255), nullable=True)
    client_image = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    closed_at = db.Column(db.DateTime, nullable=True)
    refund_amount = db.Column(db.Float, nullable=True)

    # Relationships
    payments = db.relationship('Payment', backref='contract', lazy='dynamic', cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='contract', lazy='dynamic', cascade='all, delete-orphan')
    notes_list = db.relationship('Note', backref='contract', lazy='dynamic', cascade='all, delete-orphan')
    attempts = db.relationship('ContractAttempt', backref='contract', lazy='dynamic', cascade='all, delete-orphan')
    files_employee = db.relationship('User', foreign_keys=[files_employee_id])

    def get_total_paid(self):
        return sum(p.amount for p in self.payments.filter_by(deleted=False))

    def get_remaining(self):
        return self.total_cost - self.get_total_paid()

    def get_payment_status(self):
        if self.get_remaining() <= 0:
            return 'complete'
        return 'incomplete'

    def get_visa_status_display(self):
        statuses = {'under_review': 'تحت المراجعة', 'accepted': 'تم قبول التأشيرة', 'rejected': 'تم رفض التأشيرة'}
        return statuses.get(self.visa_status, self.visa_status)

    @staticmethod
    def generate_file_number():
        from datetime import datetime
        year = datetime.now().year
        last = Contract.query.order_by(Contract.id.desc()).first()
        num = (last.id + 1) if last else 1
        return f"VIS-{year}-{num:04d}"


class Payment(db.Model):
    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.now)
    notes = db.Column(db.String(255), nullable=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    employee = db.relationship('User', foreign_keys=[employee_id])


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.now)

    uploaded_by = db.relationship('User', foreign_keys=[uploaded_by_id])


class Note(db.Model):
    __tablename__ = 'notes'

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    employee = db.relationship('User', foreign_keys=[employee_id])


class ContractAttempt(db.Model):
    """Track reapplication attempts within the same contract"""
    __tablename__ = 'contract_attempts'

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    total_cost = db.Column(db.Float, nullable=False)
    fingerprint_location = db.Column(db.String(200), nullable=True)
    attempt_number = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.now)
    employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    employee = db.relationship('User', foreign_keys=[employee_id])


class VisaApplication(db.Model):
    __tablename__ = 'visa_applications'

    id = db.Column(db.Integer, primary_key=True)
    contract_id = db.Column(db.Integer, db.ForeignKey('contracts.id'), nullable=False)
    status = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now)

    contract = db.relationship('Contract', foreign_keys=[contract_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])
