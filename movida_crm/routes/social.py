from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, session
from flask_login import login_required, current_user
from datetime import datetime
from extensions import db
from models import SocialNumber, SocialAssignment, User, Customer
from utils import log_action
from functools import wraps
import json

social_bp = Blueprint('social', __name__, url_prefix='/social')

def social_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role not in ['social', 'admin']:
            flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return login_required(decorated)

@social_bp.route('/')
@social_required
def home():
    numbers = SocialNumber.query.filter_by(employee_id=current_user.id).order_by(SocialNumber.added_at.desc()).all() if current_user.role == 'social' else SocialNumber.query.order_by(SocialNumber.added_at.desc()).all()
    total = len(numbers)
    sent = sum(1 for n in numbers if n.is_sent)
    remaining = total - sent
    sales_employees = User.query.filter_by(role='sales', is_active=True).all()
    
    # التحقق من وجود أرقام موجودة في session
    existing_numbers = session.pop('existing_numbers', None)
    show_existing_modal = request.args.get('show_existing_modal', 'false') == 'true'
    
    return render_template('social/home.html', numbers=numbers, total=total, sent=sent, remaining=remaining, sales_employees=sales_employees, existing_numbers=existing_numbers, show_existing_modal=show_existing_modal)

@social_bp.route('/add', methods=['GET', 'POST'])
@social_required
def add_number():
    if request.method == 'POST':
        phones_input = request.form.get('phone', '').strip()
        platform = request.form.get('platform', '')

        if not phones_input or not platform:
            flash('يرجى ملء جميع الحقول المطلوبة', 'danger')
            return redirect(url_for('social.home'))

        # تقسيم الأرقام المدخلة بناءً على الفاصلة
        phones = [p.strip() for p in phones_input.split(',') if p.strip()]
        
        if not phones:
            flash('يرجى إدخال رقم هاتف واحد على الأقل', 'danger')
            return redirect(url_for('social.home'))

        existing_numbers = []
        added_count = 0

        for phone in phones:
            existing = SocialNumber.query.filter_by(phone=phone).first()
            if existing:
                # بناء معلومات الرقم الموجود
                sales_name = "غير مرسل بعد"
                sales_id_val = None
                
                # التحقق من التخصيص إلى موظف سيلز
                latest_assignment = SocialAssignment.query.filter_by(
                    social_number_id=existing.id
                ).order_by(SocialAssignment.assigned_at.desc()).first()
                
                if latest_assignment:
                    sales_emp = User.query.get(latest_assignment.sales_employee_id)
                    if sales_emp:
                        sales_name = sales_emp.full_name
                        sales_id_val = sales_emp.id
                
                existing_numbers.append({
                    'id': existing.id,
                    'phone': phone,
                    'platform': existing.platform,
                    'sales_name': sales_name,
                    'sales_id': sales_id_val,
                    'is_sent': existing.is_sent
                })
            else:
                # إضافة الرقم الجديد
                number = SocialNumber(phone=phone, platform=platform, employee_id=current_user.id)
                db.session.add(number)
                db.session.flush()  # للحصول على ID
                added_count += 1
                log_action('add_social_number', f'إضافة رقم: {phone}', number.id, 'social_number')
        
        db.session.commit()

        # التعامل مع النتائج
        if added_count > 0:
            flash(f'✅ تم إضافة {added_count} رقم بنجاح', 'success')
        
        if existing_numbers:
            # حفظ البيانات في session إذا كان هناك أرقام موجودة
            session['existing_numbers'] = existing_numbers
            flash(f'⚠️ وجدنا {len(existing_numbers)} رقم موجود بالفعل في النظام', 'warning')
            return redirect(url_for('social.home', show_existing_modal='true'))

    return redirect(url_for('social.home'))

@social_bp.route('/send', methods=['POST'])
@social_required
def send_to_sales():
    number_ids = request.form.getlist('number_ids')
    sales_id = request.form.get('sales_id')

    if not number_ids or not sales_id:
        flash('يرجى اختيار الأرقام وموظف المبيعات', 'danger')
        return redirect(url_for('social.home'))

    sales_emp = User.query.filter_by(id=sales_id, role='sales', is_active=True).first()
    if not sales_emp:
        flash('موظف المبيعات غير موجود', 'danger')
        return redirect(url_for('social.home'))

    for nid in number_ids:
        number = SocialNumber.query.get(nid)
        if number:
            number.is_sent = True
            number.sent_at = datetime.now()
            assignment = SocialAssignment(
                social_number_id=number.id,
                sales_employee_id=int(sales_id),
                assigned_by_id=current_user.id
            )
            db.session.add(assignment)
            log_action('send_to_sales', f'إعادة إرسال {number.phone} إلى {sales_emp.full_name}', number.id, 'social_number')

    db.session.commit()
    flash(f'تم إرسال {len(number_ids)} رقم إلى {sales_emp.full_name}', 'success')
    return redirect(url_for('social.home'))

@social_bp.route('/performance')
@social_required
def performance():
    sales_employees = User.query.filter_by(role='sales', is_active=True).all()
    performance_data = []
    for emp in sales_employees:
        received = SocialAssignment.query.filter_by(sales_employee_id=emp.id).count()
        from_social = Customer.query.filter_by(sales_employee_id=emp.id, source='social').count()
        from_reception = Customer.query.filter_by(sales_employee_id=emp.id, source='reception').count()
        from_other = Customer.query.filter_by(sales_employee_id=emp.id, source='other').count()
        performance_data.append({
            'employee': emp,
            'received': received,
            'from_social': from_social,
            'from_reception': from_reception,
            'from_other': from_other,
            'total': from_social + from_reception + from_other
        })
    return render_template('social/performance.html', performance_data=performance_data)

@social_bp.route('/handle-existing/<int:number_id>', methods=['POST'])
@social_required
def handle_existing_number(number_id):
    """معالجة الرقم الموجود عند الإضافة المتكررة"""
    number = SocialNumber.query.get_or_404(number_id)
    option = request.form.get('existing_option')
    sales_id = request.form.get('sales_id')

    latest_assignment = SocialAssignment.query.filter_by(
        social_number_id=number.id
    ).order_by(SocialAssignment.assigned_at.desc()).first()
    existing_sales_id = latest_assignment.sales_employee_id if latest_assignment else None

    if option == 'same':
        if not existing_sales_id:
            flash('لا يوجد موظف سيلز مسجل لهذا الرقم ليتم الإرسال له تلقائياً.', 'warning')
            return redirect(url_for('social.home'))
        sales_emp = User.query.filter_by(id=existing_sales_id, role='sales', is_active=True).first()
        if not sales_emp:
            flash('الموظف السابق غير متاح، الرجاء اختيار موظف جديد.', 'warning')
            return redirect(url_for('social.home'))
        assignment = SocialAssignment(
            social_number_id=number.id,
            sales_employee_id=sales_emp.id,
            assigned_by_id=current_user.id
        )
        db.session.add(assignment)
        number.is_sent = True
        number.sent_at = datetime.now()
        db.session.commit()
        log_action('send_to_sales', f'إرسال {number.phone} لنفس موظف المبيعات {sales_emp.full_name}', number.id, 'social_number')
        flash(f'✅ تم إعادة إرسال الرقم {number.phone} إلى {sales_emp.full_name}', 'success')
        return redirect(url_for('social.home'))

    if option == 'new':
        if not sales_id:
            flash('يرجى اختيار موظف مبيعات جديد.', 'danger')
            return redirect(url_for('social.home'))
        sales_emp = User.query.filter_by(id=sales_id, role='sales', is_active=True).first()
        if not sales_emp:
            flash('موظف المبيعات غير موجود', 'danger')
            return redirect(url_for('social.home'))
        assignment = SocialAssignment(
            social_number_id=number.id,
            sales_employee_id=int(sales_id),
            assigned_by_id=current_user.id
        )
        db.session.add(assignment)
        number.is_sent = True
        number.sent_at = datetime.now()
        db.session.commit()
        log_action('send_to_sales', f'إرسال {number.phone} إلى {sales_emp.full_name}', number.id, 'social_number')
        flash(f'✅ تم إرسال الرقم {number.phone} إلى {sales_emp.full_name}', 'success')
        return redirect(url_for('social.home'))

    if option == 'keep':
        if current_user.role == 'social':
            number.employee_id = current_user.id
            db.session.commit()
        flash(f'✅ الرقم {number.phone} سيبقى في قائمة الأرقام الحالية.', 'success')
        return redirect(url_for('social.home'))

    flash('لم يتم اختيار إجراء صالح للرقم الموجود.', 'danger')
    return redirect(url_for('social.home'))

@social_bp.route('/delete/<int:number_id>', methods=['POST'])
@social_required
def delete_number(number_id):
    number = SocialNumber.query.get_or_404(number_id)
    if number.is_sent:
        flash('لا يمكن حذف رقم تم إرساله للمبيعات', 'warning')
        return redirect(url_for('social.home'))
    db.session.delete(number)
    db.session.commit()
    flash('تم حذف الرقم', 'success')
    return redirect(url_for('social.home'))

@social_bp.route('/edit/<int:number_id>', methods=['GET', 'POST'])
@social_required
def edit_number(number_id):
    """تعديل رقم اجتماعي"""
    number = SocialNumber.query.get_or_404(number_id)
    
    # التحقق من الصلاحيات
    if current_user.role == 'social' and number.employee_id != current_user.id:
        flash('لا تملك صلاحية لتعديل هذا الرقم', 'danger')
        return redirect(url_for('social.home'))
    
    if request.method == 'POST':
        new_phone = request.form.get('phone', '').strip()
        
        if not new_phone:
            flash('يرجى إدخال رقم هاتف صحيح', 'danger')
            return redirect(url_for('social.home'))
        
        # التحقق من عدم وجود الرقم الجديد في قاعدة البيانات (إذا كان مختلفاً عن الرقم الحالي)
        if new_phone != number.phone:
            existing = SocialNumber.query.filter_by(phone=new_phone).first()
            if existing:
                flash(f'❌ الرقم {new_phone} موجود بالفعل في النظام', 'danger')
                return redirect(url_for('social.home'))
        
        old_phone = number.phone
        number.phone = new_phone
        db.session.commit()
        log_action('edit_social_number', f'تعديل رقم من {old_phone} إلى {new_phone}', number.id, 'social_number')
        flash(f'✅ تم تعديل الرقم بنجاح من {old_phone} إلى {new_phone}', 'success')
        return redirect(url_for('social.home'))
    
    return render_template('social/edit_number.html', number=number)
