from datetime import datetime
from extensions import db

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    reference_type = db.Column(db.String(30), nullable=True)  # customer, contract, payment, etc.
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    ACTION_LABELS = {
        'login': 'تسجيل الدخول',
        'logout': 'تسجيل الخروج',
        'add_customer': 'إضافة عميل',
        'edit_customer': 'تعديل عميل',
        'add_followup': 'إضافة متابعة',
        'add_interview': 'إضافة مقابلة',
        'add_contract': 'إضافة تعاقد',
        'add_payment': 'إضافة دفعة',
        'edit_payment': 'تعديل دفعة',
        'delete_payment': 'حذف دفعة',
        'upload_document': 'رفع ملف',
        'update_visa_status': 'تعديل حالة التأشيرة',
        'close_contract': 'إغلاق ملف',
        'reapply': 'إعادة تقديم',
        'add_social_number': 'إضافة رقم سوشيال',
        'send_to_sales': 'إرسال للسيلز',
        'no_answer': 'لم يتم الرد',
        'add_note': 'إضافة ملاحظة',
        'update_fingerprint': 'تعديل التبصيم',
        'add_user': 'إضافة مستخدم',
        'edit_user': 'تعديل مستخدم',
        'delete_user': 'حذف مستخدم',
    }

    def get_action_display(self):
        return self.ACTION_LABELS.get(self.action, self.action)
