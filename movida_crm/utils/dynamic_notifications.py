from datetime import datetime, timedelta
from extensions import db
from models.notification import Notification
from models.customer import Customer
from models.contract import Contract

def get_dynamic_notifications(user_id, user_role):
    """
    احسب الإشعارات الديناميكية بناءً على المقابلات والمتابعات والتبصيم القادمة
    الإشعارات تظهر فقط في يوم الحدث وتختفي بعده تلقائياً
    """
    notifications = []
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    tomorrow_start = today_end
    tomorrow_end = tomorrow_start + timedelta(days=1)
    
    if user_role == 'sales':
        # المقابلات في نطاق اليوم الحالي
        today_interviews = Customer.query.filter(
            Customer.sales_employee_id == user_id,
            Customer.interview_date >= today_start,
            Customer.interview_date < today_end
        ).order_by(Customer.interview_date).all()
        
        for customer in today_interviews:
            notifications.append({
                'id': f'dynamic_interview_{customer.id}',
                'title': f"🔴 مقابلة اليوم",
                'message': f'{customer.full_name} ({customer.phone}) - {customer.interview_date.strftime("%H:%M")}',
                'type': 'interview',
                'created_at': customer.interview_date,
                'is_dynamic': True,
                'status': '🔴 مهم جداً'
            })
        
        # المقابلات في غد
        tomorrow_interviews = Customer.query.filter(
            Customer.sales_employee_id == user_id,
            Customer.interview_date >= tomorrow_start,
            Customer.interview_date < tomorrow_end
        ).order_by(Customer.interview_date).all()
        
        for customer in tomorrow_interviews:
            notifications.append({
                'id': f'dynamic_interview_{customer.id}',
                'title': f"🟡 مقابلة غداً",
                'message': f'{customer.full_name} ({customer.phone}) - {customer.interview_date.strftime("%H:%M")}',
                'type': 'interview',
                'created_at': customer.interview_date,
                'is_dynamic': True,
                'status': '🟡 قريب'
            })
        
        # المتابعات في اليوم
        today_followups = Customer.query.filter(
            Customer.sales_employee_id == user_id,
            Customer.followup_date >= today_start,
            Customer.followup_date < today_end
        ).order_by(Customer.followup_date).all()
        
        for customer in today_followups:
            notifications.append({
                'id': f'dynamic_followup_{customer.id}',
                'title': f"🔴 متابعة اليوم",
                'message': f'{customer.full_name} ({customer.phone}) - {customer.followup_date.strftime("%H:%M")}',
                'type': 'followup',
                'created_at': customer.followup_date,
                'is_dynamic': True,
                'status': '🔴 مهم جداً'
            })
        
        # المتابعات في غد
        tomorrow_followups = Customer.query.filter(
            Customer.sales_employee_id == user_id,
            Customer.followup_date >= tomorrow_start,
            Customer.followup_date < tomorrow_end
        ).order_by(Customer.followup_date).all()
        
        for customer in tomorrow_followups:
            notifications.append({
                'id': f'dynamic_followup_{customer.id}',
                'title': f"🟡 متابعة غداً",
                'message': f'{customer.full_name} ({customer.phone}) - {customer.followup_date.strftime("%H:%M")}',
                'type': 'followup',
                'created_at': customer.followup_date,
                'is_dynamic': True,
                'status': '🟡 قريب'
            })
    
    elif user_role == 'files':
        # مواعيد التبصيم خلال الثلاث أسابيع القادمة
        max_alert_date = now + timedelta(days=21)
        upcoming_fingerprints = Contract.query.filter(
            Contract.fingerprint_date >= today_start,
            Contract.fingerprint_date <= max_alert_date,
            Contract.status == 'active'
        ).order_by(Contract.fingerprint_date).all()

        for contract in upcoming_fingerprints:
            delta_days = (contract.fingerprint_date.date() - now.date()).days
            if delta_days < 0:
                title = f"🔴 تبصيم متأخر"
                status = '🔴 مهم جداً'
                bg = '#fee2e2'
            elif delta_days >= 14:
                title = f"🟢 تبصيم بعد 3 أسابيع"
                status = '🟢 جاهز'
                bg = '#dcfce7'
            elif delta_days >= 7:
                title = f"🟡 تبصيم بعد أسبوعين"
                status = '🟡 قريب'
                bg = '#fef3c7'
            else:
                title = f"🔴 تبصيم هذا الأسبوع"
                status = '🔴 مهم جداً'
                bg = '#fee2e2'

            notifications.append({
                'id': f'dynamic_fingerprint_{contract.id}',
                'title': title,
                'message': f'{contract.client_name} - {contract.fingerprint_location or "بدون موقع"} - {contract.fingerprint_date.strftime("%Y-%m-%d %Y-%m-%d %H:%M")}',
                'type': 'fingerprint',
                'created_at': contract.fingerprint_date,
                'is_dynamic': True,
                'status': status,
                'bg': bg
            })
    
    elif user_role == 'admin':
        # Admin يرى كل شيء
        # المقابلات اليوم
        today_interviews = Customer.query.filter(
            Customer.interview_date >= today_start,
            Customer.interview_date < today_end
        ).order_by(Customer.interview_date).all()
        
        for customer in today_interviews:
            notifications.append({
                'id': f'dynamic_interview_{customer.id}',
                'title': f"🔴 مقابلة اليوم",
                'message': f'{customer.full_name} ({customer.phone}) - {customer.interview_date.strftime("%H:%M")}',
                'type': 'interview',
                'created_at': customer.interview_date,
                'is_dynamic': True,
                'status': '🔴 مهم جداً'
            })
        
        # المقابلات غداً
        tomorrow_interviews = Customer.query.filter(
            Customer.interview_date >= tomorrow_start,
            Customer.interview_date < tomorrow_end
        ).order_by(Customer.interview_date).all()
        
        for customer in tomorrow_interviews:
            notifications.append({
                'id': f'dynamic_interview_{customer.id}',
                'title': f"🟡 مقابلة غداً",
                'message': f'{customer.full_name} ({customer.phone}) - {customer.interview_date.strftime("%H:%M")}',
                'type': 'interview',
                'created_at': customer.interview_date,
                'is_dynamic': True,
                'status': '🟡 قريب'
            })
        
        # المتابعات اليوم
        today_followups = Customer.query.filter(
            Customer.followup_date >= today_start,
            Customer.followup_date < today_end
        ).order_by(Customer.followup_date).all()
        
        for customer in today_followups:
            notifications.append({
                'id': f'dynamic_followup_{customer.id}',
                'title': f"🔴 متابعة اليوم",
                'message': f'{customer.full_name} ({customer.phone}) - {customer.followup_date.strftime("%H:%M")}',
                'type': 'followup',
                'created_at': customer.followup_date,
                'is_dynamic': True,
                'status': '🔴 مهم جداً'
            })
        
        # المتابعات غداً
        tomorrow_followups = Customer.query.filter(
            Customer.followup_date >= tomorrow_start,
            Customer.followup_date < tomorrow_end
        ).order_by(Customer.followup_date).all()
        
        for customer in tomorrow_followups:
            notifications.append({
                'id': f'dynamic_followup_{customer.id}',
                'title': f"🟡 متابعة غداً",
                'message': f'{customer.full_name} ({customer.phone}) - {customer.followup_date.strftime("%H:%M")}',
                'type': 'followup',
                'created_at': customer.followup_date,
                'is_dynamic': True,
                'status': '🟡 قريب'
            })
        
        # التبصيم خلال الثلاث أسابيع القادمة
        max_alert_date = now + timedelta(days=21)
        upcoming_fingerprints = Contract.query.filter(
            Contract.fingerprint_date >= today_start,
            Contract.fingerprint_date <= max_alert_date,
            Contract.status == 'active'
        ).order_by(Contract.fingerprint_date).all()

        for contract in upcoming_fingerprints:
            delta_days = (contract.fingerprint_date.date() - now.date()).days
            if delta_days < 0:
                title = f"🔴 تبصيم متأخر"
                status = '🔴 مهم جداً'
                bg = '#fee2e2'
            elif delta_days >= 14:
                title = f"🟢 تبصيم بعد 3 أسابيع"
                status = '🟢 جاهز'
                bg = '#dcfce7'
            elif delta_days >= 7:
                title = f"🟡 تبصيم بعد أسبوعين"
                status = '🟡 قريب'
                bg = '#fef3c7'
            else:
                title = f"🔴 تبصيم هذا الأسبوع"
                status = '🔴 مهم جداً'
                bg = '#fee2e2'

            notifications.append({
                'id': f'dynamic_fingerprint_{contract.id}',
                'title': title,
                'message': f'{contract.client_name} - {contract.fingerprint_location or "بدون موقع"} - {contract.fingerprint_date.strftime("%Y-%m-%d %H:%M")}',
                'type': 'fingerprint',
                'created_at': contract.fingerprint_date,
                'is_dynamic': True,
                'status': status,
                'bg': bg
            })
    
    # احصل على الإشعارات المخزنة في قاعدة البيانات (إشعارات ثابتة)
    if user_role == 'admin':
        db_notifications = Notification.query.filter_by(is_read=False).order_by(Notification.created_at.desc()).all()
    else:
        db_notifications = Notification.query.filter_by(user_id=user_id, is_read=False).order_by(Notification.created_at.desc()).all()
    
    # حول DB notifications إلى دكاموشن
    for notif in db_notifications:
        notifications.append({
            'id': f'db_{notif.id}',
            'title': notif.title,
            'message': notif.message,
            'type': notif.type,
            'created_at': notif.created_at,
            'is_dynamic': False,
            'status': '📬 جديد'
        })
    
    # رتّب حسب التاريخ (الأحدث والأهم أولاً)
    # أولاً: إشعارات اليوم (مهم جداً)
    # ثانياً: إشعارات غداً (قريب)
    # ثالثاً: إشعارات مخزنة
    notifications.sort(key=lambda x: (
        0 if '🔴' in x['status'] else (1 if '🟡' in x['status'] else 2),
        -x['created_at'].timestamp() if hasattr(x['created_at'], 'timestamp') else 0
    ))
    
    return notifications

