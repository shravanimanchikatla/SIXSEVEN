import os
import time
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from flask_migrate import upgrade, stamp
from app import app, db
from models import User, AdminRole

def create_database_if_not_exists():
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL not found in environment.")
        return False
    
    # Parse standard connection string: postgresql://user:password@host:port/dbname
    try:
        parts = db_url.replace("postgresql://", "").split("/")
        dbname = parts[1].split('?')[0] # get db name, remove query params
        
        auth_host = parts[0].split('@')
        user_pass = auth_host[0].split(':')
        user = user_pass[0]
        password = user_pass[1] if len(user_pass) > 1 else ""
        
        host_port = auth_host[1].split(':')
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else "5432"
    except Exception as e:
        print(f"Error parsing DATABASE_URL: {e}")
        return False
        
    print(f"Connecting to default postgres database on {host}:{port}...")
    try:
        conn = psycopg2.connect(
            dbname='postgres',
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (dbname,))
        exists = cur.fetchone()
        
        if not exists:
            print(f"Database '{dbname}' does not exist. Creating it now...")
            cur.execute(f"CREATE DATABASE {dbname}")
            print(f"Database '{dbname}' created successfully.")
        else:
            print(f"Database '{dbname}' already exists.")
            
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error connecting to PostgreSQL server: {e}")
        print("Please ensure PostgreSQL is running and credentials in .env are correct.")
        return False

def init_db():
    print("Starting Database Initialization...")
    if not create_database_if_not_exists():
        print("Could not verify or create database. Exiting.")
        return
        
    with app.app_context():
        print("Running schema creation via SQLAlchemy...")
        # Since this is a fresh DB migration, we can either use db.create_all() 
        # or flask-migrate commands. The prompt asked to create tables and apply migrations.
        # It's usually better to let Flask-Migrate do it if a migrations folder exists.
        
        if not os.path.exists('migrations'):
            print("No 'migrations' folder found. Initializing Flask-Migrate...")
            os.system('flask db init')
            print("Creating initial migration...")
            os.system('flask db migrate -m "Initial schema creation"')
            
        print("Applying migrations...")
        os.system('flask db upgrade')
        
        print("Seeding initial Admin roles...")
        # Seed default admin if none exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("Creating default 'admin' user...")
            # Note: In production, password should be hashed via Werkzeug.
            admin = User(username='admin', email='admin@safesphere.local', password_hash='pbkdf2:sha256:150000$DEFAULT$HASH')
            db.session.add(admin)
            db.session.commit()
            
            role = AdminRole(user_id=admin.id, role_name='SUPERADMIN')
            db.session.add(role)
            db.session.commit()
            print("Admin user created successfully.")
        else:
            print("Admin user already exists. Skipping seed.")
            
        print("Database initialization complete! You can now run `python app.py`.")

if __name__ == "__main__":
    init_db()
