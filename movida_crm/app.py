import os
import sys
from flask import Flask
from config import Config
from extensions import db, migrate, login_manager
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

# Ensure stdout/stderr use UTF-8 encoding to avoid UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    # Older Python runtimes or redirected streams may not support reconfigure
    pass

def should_initialize_db():
    if os.environ.get('FLASK_SKIP_DB_SETUP') == '1':
        return False

    cli_args = [arg.lower() for arg in sys.argv[1:]]
    if any(arg in {'db', 'migrate', 'init', 'upgrade', 'downgrade', 'stamp', 'current'} for arg in cli_args):
        return False

    return True


def create_app(init_db=True):
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # User loader
    from models.user import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from routes.auth import auth_bp
    from routes.social import social_bp
    from routes.sales import sales_bp
    from routes.files import files_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(social_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(admin_bp)

    # Context processors
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from utils.dynamic_notifications import get_dynamic_notifications
        notif_count = 0
        notifs = []
        if current_user.is_authenticated and current_user.role in ['sales', 'admin', 'files']:
            notifs = get_dynamic_notifications(current_user.id, current_user.role)
            notif_count = len(notifs)
        return dict(notif_count=notif_count, topbar_notifications=notifs[:10])

    # Ensure schema and create missing tables when needed.
    # Local SQLite still seeds data automatically; Postgres/Supabase will be created if empty.
    if init_db:
        if not _has_any_table(app):
            create_database_structure(app)
        else:
            _ensure_customer_schema(app)

    return app


def _is_local_sqlite(app):
    return app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:///')


def _has_any_table(app):
    with app.app_context():
        engine = getattr(db, 'engine', None)
        if engine is None:
            try:
                engine = db.get_engine()
            except Exception:
                engine = db.engines.get(None)
        try:
            inspector = inspect(engine)
            return bool(inspector.get_table_names())
        except OperationalError as exc:
            app.logger.warning('Database not reachable when checking tables: %s', exc)
            return False
        except Exception as exc:
            app.logger.warning('Unexpected error checking database tables: %s', exc)
            return False


def create_database_structure(app):
    with app.app_context():
        try:
            db.create_all()
            if _is_local_sqlite(app):
                seed_data()
            print('✅ Database structure created successfully')
        except Exception as exc:
            print(f'⚠️ Database structure creation skipped: {exc}')
            app.logger.warning('Database structure creation skipped: %s', exc)


def _ensure_customer_schema(app):
    with app.app_context():
        engine = getattr(db, 'engine', None)
        if engine is None:
            try:
                engine = db.get_engine()
            except Exception:
                engine = db.engines.get(None)
        try:
            inspector = inspect(engine)
            if 'customers' not in inspector.get_table_names():
                return False

            existing_columns = [col['name'] for col in inspector.get_columns('customers')]
            missing_columns = []
            if 'interview_status' not in existing_columns:
                missing_columns.append('ALTER TABLE customers ADD COLUMN interview_status VARCHAR(20)')
            if 'interview_result' not in existing_columns:
                missing_columns.append('ALTER TABLE customers ADD COLUMN interview_result VARCHAR(20)')

            if not missing_columns:
                return False

            with engine.begin() as connection:
                for sql in missing_columns:
                    connection.execute(text(sql))
            return True
        except OperationalError as exc:
            app.logger.warning('Database not reachable when ensuring customer schema: %s', exc)
            return False
        except Exception as exc:
            app.logger.warning('Unexpected error ensuring customer schema: %s', exc)
            return False


def initialize_database(app):
    with app.app_context():
        try:
            _ensure_customer_schema(app)
            db.create_all()
            seed_data()
            print("✅ Database initialized successfully")
        except Exception as exc:
            print(f"⚠️ Database initialization skipped: {exc}")
            app.logger.warning("Database initialization skipped: %s", exc)


def seed_data():
    """Create default admin user and sample data if DB is empty"""
    from models.user import User
    if User.query.first():
        return

    print("🌱 Creating seed data...")

    # Admin
    admin = User(username='admin', full_name='المدير العام', role='admin', email='admin@crm.com')
    admin.set_password('admin123')
    db.session.add(admin)

    # Sales employees
    sales1 = User(username='sales1', full_name='أحمد محمد', role='sales')
    sales1.set_password('sales123')
    db.session.add(sales1)

    sales2 = User(username='sales2', full_name='سارة علي', role='sales')
    sales2.set_password('sales123')
    db.session.add(sales2)

    # Social employee
    social1 = User(username='social1', full_name='محمد حسن', role='social')
    social1.set_password('social123')
    db.session.add(social1)

    # Files employee
    files1 = User(username='files1', full_name='نورا إبراهيم', role='files')
    files1.set_password('files123')
    db.session.add(files1)

    db.session.commit()

    # Sample social numbers
    from models.social import SocialNumber, SocialAssignment
    from datetime import datetime, timedelta

    platforms = ['Facebook', 'Instagram', 'TikTok', 'WhatsApp']
    for i in range(1, 11):
        sn = SocialNumber(
            phone=f'01{str(i).zfill(9)}',
            platform=platforms[i % len(platforms)],
            employee_id=social1.id,
            is_sent=i <= 5,
            sent_at=datetime.now() if i <= 5 else None
        )
        db.session.add(sn)

    db.session.commit()

    # Assign first 5 numbers to sales1
    numbers = SocialNumber.query.limit(5).all()
    for sn in numbers:
        assignment = SocialAssignment(
            social_number_id=sn.id,
            sales_employee_id=sales1.id,
            assigned_by_id=social1.id
        )
        db.session.add(assignment)

    db.session.commit()

    # Sample customers
    from models.customer import Customer, CustomerCountry
    customers_data = [
        {'phone': '0501234567', 'full_name': 'خالد عبدالله', 'source': 'social', 'interest': 'interested', 'pct': 80},
        {'phone': '0502345678', 'full_name': 'فاطمة الزهراء', 'source': 'reception', 'interest': 'interested', 'pct': 65},
        {'phone': '0503456789', 'full_name': 'عمر الشريف', 'source': 'other', 'interest': 'not_interested', 'pct': None},
        {'phone': '0504567890', 'full_name': 'منى حسين', 'source': 'social', 'interest': 'interested', 'pct': 90},
        {'phone': '0505678901', 'full_name': 'يوسف كمال', 'source': 'social', 'interest': None, 'pct': None},
    ]

    countries_map = ['كندا', 'أمريكا', 'ألمانيا', 'المملكة المتحدة', 'فرنسا']

    for i, cd in enumerate(customers_data):
        c = Customer(
            phone=cd['phone'],
            full_name=cd['full_name'],
            has_bank_statement=i % 2 == 0,
            interest_level=cd['interest'],
            interest_percentage=cd['pct'],
            source=cd['source'],
            sales_employee_id=sales1.id,
            interview_date=datetime.now() + timedelta(days=i+1) if i < 3 else None,
            followup_date=datetime.now() + timedelta(days=i+2) if i < 3 else None,
        )
        db.session.add(c)
        db.session.flush()
        db.session.add(CustomerCountry(customer_id=c.id, country=countries_map[i % len(countries_map)]))

    db.session.commit()

    # Sample contracts
    from models.contract import Contract, Payment, Note
    contracts_data = [
        {'name': 'خالد عبدالله', 'phone': '0601000001', 'country': 'كندا', 'cost': 15000, 'paid': 8000},
        {'name': 'فاطمة الزهراء', 'phone': '0601000002', 'country': 'أمريكا', 'cost': 20000, 'paid': 20000},
        {'name': 'عمر الشريف', 'phone': '0601000003', 'country': 'ألمانيا', 'cost': 12000, 'paid': 6000},
    ]

    for i, cd in enumerate(contracts_data):
        contract = Contract(
            file_number=f'VIS-2024-{i+1:04d}',
            client_phone=cd['phone'],
            client_name=cd['name'],
            country=cd['country'],
            total_cost=cd['cost'],
            num_payments=3,
            fingerprint_location='مكتب التأشيرات - القاهرة',
            fingerprint_date=datetime.now() + timedelta(days=7 + i * 3),
            sales_employee_name=sales1.full_name,
            files_employee_id=files1.id,
            visa_status='accepted' if i == 1 else 'under_review'
        )
        db.session.add(contract)
        db.session.flush()

        # Add payment
        p = Payment(
            contract_id=contract.id,
            amount=cd['paid'],
            employee_id=files1.id,
            notes='دفعة أولى'
        )
        db.session.add(p)

        # Add note
        n = Note(contract_id=contract.id, content='تم استلام الملف وجاري المراجعة', employee_id=files1.id)
        db.session.add(n)

    db.session.commit()
    print("✅ Seed data created successfully!")
    print("\n📋 Default accounts:")
    print("   Admin:  admin / admin123")
    print("   Sales:  sales1 / sales123")
    print("   Social: social1 / social123")
    print("   Files:  files1 / files123")


app = create_app(init_db=should_initialize_db())

if __name__ == '__main__':
    print("\n🚀 Starting CRM Server...")
    print("   URL: http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
