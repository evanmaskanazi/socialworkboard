"""
Initialize Database Script
Run this to set up the database with initial data
"""

from new_backend import app, db, User, Therapist, Client, TrackingCategory, bcrypt
from datetime import datetime
import os

def init_database():
    """Initialize the database with tables and default data"""
    with app.app_context():
        # Create all tables
        print("Creating database tables...")
        db.create_all()
        
        # Check if already initialized
        if TrackingCategory.query.count() > 0:
            print("Database already initialized!")
            return
        
        # Add default tracking categories
        print("Adding default tracking categories...")
        default_categories = [
            TrackingCategory(
                name='Emotion Level',
                description='Overall emotional state',
                is_default=True
            ),
            TrackingCategory(
                name='Energy',
                description='Physical and mental energy levels',
                is_default=True
            ),
            TrackingCategory(
                name='Social Activity',
                description='Engagement in social interactions',
                is_default=True
            ),
            TrackingCategory(
                name='Sleep Quality',
                description='Quality of sleep',
                is_default=False
            ),
            TrackingCategory(
                name='Anxiety Level',
                description='Level of anxiety experienced',
                is_default=False
            ),
            TrackingCategory(
                name='Motivation',
                description='Level of motivation and drive',
                is_default=False
            )
        ]
        
        for category in default_categories:
            db.session.add(category)
        
        # Create demo therapist account (optional)
        if os.environ.get('CREATE_DEMO_ACCOUNTS', 'false').lower() == 'true':
            print("Creating demo therapist account...")
            
            # Check if demo account already exists
            if not User.query.filter_by(email='demo.therapist@example.com').first():
                demo_therapist_user = User(
                    email='demo.therapist@example.com',
                    password_hash=bcrypt.generate_password_hash('demo123').decode('utf-8'),
                    role='therapist',
                    is_active=True
                )
                db.session.add(demo_therapist_user)
                db.session.flush()
                
                demo_therapist = Therapist(
                    user_id=demo_therapist_user.id,
                    license_number='DEMO-12345',
                    name='Dr. Demo Therapist',
                    organization='Demo Mental Health Clinic',
                    specializations=['Anxiety', 'Depression', 'Stress Management']
                )
                db.session.add(demo_therapist)
                
                print("Demo therapist created:")
                print("  Email: demo.therapist@example.com")
                print("  Password: demo123")
                print("  License: DEMO-12345")
        
        # Commit all changes
        db.session.commit()
        print("Database initialization complete!")

if __name__ == '__main__':
    print("=" * 60)
    print("Therapeutic Companion - Database Initialization")
    print("=" * 60)
    
    # Check if we're in production
    if os.environ.get('PRODUCTION'):
        print("Running in PRODUCTION mode")
    else:
        print("Running in DEVELOPMENT mode")
    
    # Check database URL
    db_url = os.environ.get('DATABASE_URL', 'Not set')
    if db_url != 'Not set':
        # Hide password in output
        if '@' in db_url:
            parts = db_url.split('@')
            safe_url = parts[0].split('//')[0] + '//***:***@' + parts[1]
            print(f"Database URL: {safe_url}")
        else:
            print(f"Database URL: {db_url}")
    else:
        print("WARNING: DATABASE_URL not set, using default")
    
    try:
        init_database()
        print("\n✅ Success! Database is ready.")
    except Exception as e:
        print(f"\n❌ Error during initialization: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure PostgreSQL is running")
        print("2. Check DATABASE_URL environment variable")
        print("3. Ensure database user has proper permissions")
        exit(1)