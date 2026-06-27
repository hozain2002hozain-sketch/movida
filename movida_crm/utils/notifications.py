from datetime import datetime, timedelta
from extensions import db
from models.notification import Notification

def create_interview_notification(user_id, customer_name, phone, interview_date, is_sales=True):
    """إنشاء إشعار مقابلة"""
    if not user_id or not interview_date:
        return
    
    now = datetime.now()
    source = "مبيعات" if is_sales else "ملفات"
    
    # إشعار فوري عند الإنشاء
    n = Notification(
        user_id=user_id,
        title=f'مقابلة جديدة من {source}',
        message=f'{customer_name} ({phone}) - موعد: {interview_date.strftime("%Y-%m-%d %H:%M")}',
        type='interview',
        reference_id=user_id,
        reference_type='interview'
    )
    db.session.add(n)
    
    # إشعار تذكيري قبل اليوم
    if interview_date > now:
        notif_time = interview_date - timedelta(days=1)
        if notif_time > now:
            n2 = Notification(
                user_id=user_id,
                title='تذكير: مقابلة غداً',
                message=f'{customer_name} ({phone}) - الساعة {interview_date.strftime("%H:%M")}',
                type='interview',
                reference_id=user_id,
                reference_type='interview'
            )
            db.session.add(n2)


def create_followup_notification(user_id, customer_name, phone, followup_date):
    """إشعار متابعة"""
    if not user_id or not followup_date:
        return
    
    now = datetime.now()
    
    # إشعار فوري عند الإنشاء
    n = Notification(
        user_id=user_id,
        title='متابعة جديدة',
        message=f'{customer_name} ({phone}) - موعد: {followup_date.strftime("%Y-%m-%d %H:%M")}',
        type='followup',
        reference_id=user_id,
        reference_type='followup'
    )
    db.session.add(n)
    
    # إشعار تذكيري قبل اليوم
    if followup_date > now:
        notif_time = followup_date - timedelta(days=1)
        if notif_time > now:
            n2 = Notification(
                user_id=user_id,
                title='تذكير: متابعة غداً',
                message=f'{customer_name} ({phone}) - الساعة {followup_date.strftime("%H:%M")}',
                type='followup',
                reference_id=user_id,
                reference_type='followup'
            )
            db.session.add(n2)


def create_fingerprint_notification(user_id, client_name, fingerprint_date, location):
    """إشعار تبصيم"""
    if not user_id or not fingerprint_date:
        return
    
    now = datetime.now()
    
    # إشعار فوري عند الإنشاء
    n = Notification(
        user_id=user_id,
        title='موعد تبصيم جديد',
        message=f'{client_name} - {location or "بدون موقع"} - {fingerprint_date.strftime("%Y-%m-%d %H:%M")}',
        type='fingerprint',
        reference_id=user_id,
        reference_type='fingerprint'
    )
    db.session.add(n)
    
    # إشعار تذكيري قبل اليوم
    if fingerprint_date > now:
        notif_time = fingerprint_date - timedelta(days=1)
        if notif_time > now:
            n2 = Notification(
                user_id=user_id,
                title='تذكير: تبصيم غداً',
                message=f'{client_name} - الساعة {fingerprint_date.strftime("%H:%M")}',
                type='fingerprint',
                reference_id=user_id,
                reference_type='fingerprint'
            )
            db.session.add(n2)
