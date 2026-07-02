from datetime import datetime, timedelta
from sqlalchemy import or_
from models.customer import Customer

def get_dynamic_notifications(user_id, user_role):
    """
    احسب الإشعارات الديناميكية بناءً على مواعيد المقابلات فقط.
    الإشعارات تظهر اليوم أو غداً ثم تختفي بعد يوم الحدث.
    """
    notifications = []
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    tomorrow_start = today_end
    tomorrow_end = tomorrow_start + timedelta(days=1)

    active_status_filter = or_(Customer.interview_status == 'active', Customer.interview_status.is_(None), Customer.interview_status == 'attended')

    if user_role == 'sales':
        interview_filter = Customer.query.filter(
            Customer.sales_employee_id == user_id,
            Customer.interview_date.isnot(None),
            Customer.interview_date >= today_start,
            Customer.interview_date < tomorrow_end,
            active_status_filter
        ).order_by(Customer.interview_date).all()
    else:
        interview_filter = Customer.query.filter(
            Customer.interview_date.isnot(None),
            Customer.interview_date >= today_start,
            Customer.interview_date < tomorrow_end,
            active_status_filter
        ).order_by(Customer.interview_date).all()

    for customer in interview_filter:
        if today_start <= customer.interview_date < today_end:
            title = '🔴 مقابلة اليوم'
            status = '🔴 مهم جداً'
        else:
            title = '🟡 مقابلة غداً'
            status = '🟡 قريب'

        notifications.append({
            'id': f'dynamic_interview_{customer.id}',
            'title': title,
            'message': f'{customer.full_name} ({customer.phone}) - {customer.interview_date.strftime("%H:%M")}',
            'type': 'interview',
            'created_at': customer.interview_date,
            'is_dynamic': True,
            'status': status
        })

    notifications.sort(key=lambda x: (
        0 if '🔴' in x['status'] else (1 if '🟡' in x['status'] else 2),
        -x['created_at'].timestamp() if hasattr(x['created_at'], 'timestamp') else 0
    ))

    return notifications

