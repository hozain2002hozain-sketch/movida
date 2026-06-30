from datetime import datetime
from extensions import db

class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    has_bank_statement = db.Column(db.Boolean, default=False)
    interest_level = db.Column(db.String(20), nullable=True)  # interested, not_interested
    interest_percentage = db.Column(db.Integer, nullable=True)
    not_interested_reason = db.Column(db.String(255), nullable=True)
    source = db.Column(db.String(30), nullable=False, default='social')  # social, reception, other, files
    source_detail = db.Column(db.String(100), nullable=True)
    social_number_id = db.Column(db.Integer, db.ForeignKey('social_numbers.id'), nullable=True)
    sales_employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    interview_date = db.Column(db.DateTime, nullable=True)
    interview_status = db.Column(db.String(20), nullable=True, default='active')  # active, missed, attended
    interview_result = db.Column(db.String(20), nullable=True)  # contract, interview
    interview_action_at = db.Column(db.DateTime, nullable=True)  # تاريخ تسجيل الإجراء
    followup_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    countries = db.relationship('CustomerCountry', backref='customer', lazy='dynamic', cascade='all, delete-orphan')
    followups = db.relationship('FollowUp', backref='customer', lazy='dynamic', cascade='all, delete-orphan')
    interviews = db.relationship('Interview', backref='customer', lazy='dynamic', cascade='all, delete-orphan')
    social_number = db.relationship('SocialNumber', backref='customer', uselist=False)

    def get_source_display(self):
        sources = {
            'social': 'سوشيال ميديا',
            'reception': 'استقبال',
            'files': 'قسم الملفات',
            'other': 'مصدر آخر'
        }
        return sources.get(self.source, self.source)

    def get_interview_status_display(self):
        statuses = {
            'active': 'مجدولة',
            'missed': 'لم يحضر',
            'attended': 'حضر'
        }
        return statuses.get(self.interview_status, self.interview_status or '-')

    def get_interview_result_display(self):
        results = {
            'contract': 'تحويل لتعاقد',
            'interview': 'حجز مقابلة'
        }
        return results.get(self.interview_result, self.interview_result or '-')

    def get_countries_list(self):
        return [c.country for c in self.countries]


class CustomerCountry(db.Model):
    __tablename__ = 'customer_countries'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    country = db.Column(db.String(100), nullable=False)


class NoAnswerNumber(db.Model):
    __tablename__ = 'no_answer_numbers'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), nullable=False, index=True)
    sales_employee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.now)
    social_number_id = db.Column(db.Integer, db.ForeignKey('social_numbers.id'), nullable=True)

    sales_employee = db.relationship('User', foreign_keys=[sales_employee_id])
    social_number = db.relationship('SocialNumber', foreign_keys=[social_number_id])
