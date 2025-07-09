"""
Migration Script: JSON to PostgreSQL
Transfers existing data from JSON files to the new database
"""

import os
import json
from datetime import datetime, date
from pathlib import Path
from new_backend import app, db, User, Therapist, Client, DailyCheckin, WeeklyGoal, TherapistNote, TrackingCategory, ClientTrackingPlan, bcrypt

def migrate_data():
    """Migrate all JSON data to PostgreSQL"""
    with app.app_context():
        print("Starting migration from JSON to PostgreSQL...")
        
        # Ensure database is initialized
        db.create_all()
        
        # Check if categories exist
        if TrackingCategory.query.count() == 0:
            print("Initializing tracking categories...")
            init_tracking_categories()
        
        # Migrate therapists
        therapists_migrated = migrate_therapists()
        print(f"Migrated {therapists_migrated} therapists")
        
        # Migrate patients/clients
        clients_migrated = migrate_clients()
        print(f"Migrated {clients_migrated} clients")
        
        # Migrate check-ins
        checkins_migrated = migrate_checkins()
        print(f"Migrated {checkins_migrated} check-ins")
        
        print("\nMigration complete!")
        print("\nSummary:")
        print(f"- Therapists: {therapists_migrated}")
        print(f"- Clients: {clients_migrated}")
        print(f"- Check-ins: {checkins_migrated}")

def init_tracking_categories():
    """Initialize default tracking categories"""
    categories = [
        ('Emotion Level', 'Overall emotional state', True),
        ('Energy', 'Physical and mental energy levels', True),
        ('Social Activity', 'Engagement in social interactions', True),
        ('Sleep Quality', 'Quality of sleep', False),
        ('Anxiety Level', 'Level of anxiety experienced', False),
        ('Motivation', 'Level of motivation and drive', False)
    ]
    
    for name, desc, is_default in categories:
        cat = TrackingCategory(name=name, description=desc, is_default=is_default)
        db.session.add(cat)
    
    db.session.commit()

def migrate_therapists():
    """Migrate therapist data from JSON files"""
    count = 0
    therapists_dir = Path('therapy_data/therapists')
    
    if not therapists_dir.exists():
        print("No therapists directory found")
        return 0
    
    # Create a default therapist for orphaned clients
    default_user = User(
        email='default.therapist@system.local',
        password_hash=bcrypt.generate_password_hash('system_generated_' + os.urandom(16).hex()).decode('utf-8'),
        role='therapist',
        is_active=True
    )
    db.session.add(default_user)
    db.session.flush()
    
    default_therapist = Therapist(
        user_id=default_user.id,
        license_number='SYSTEM-DEFAULT',
        name='System Default Therapist',
        organization='Legacy Data Migration'
    )
    db.session.add(default_therapist)
    db.session.flush()
    
    therapist_map = {}  # Map old email to new therapist ID
    
    for file_path in therapists_dir.glob('*.json'):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Check if already migrated
            if User.query.filter_by(email=data['email']).first():
                print(f"Therapist {data['email']} already exists, skipping...")
                continue
            
            # Create user account
            user = User(
                email=data['email'],
                password_hash=data.get('password_hash', bcrypt.generate_password_hash('temp_password').decode('utf-8')),
                role='therapist',
                is_active=data.get('active', True),
                created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
            )
            db.session.add(user)
            db.session.flush()
            
            # Create therapist profile
            therapist = Therapist(
                user_id=user.id,
                license_number=data.get('license_number', f"LEGACY-{count}"),
                name=data['name'],
                organization=data.get('organization', ''),
                specializations=data.get('specializations', [])
            )
            db.session.add(therapist)
            db.session.flush()
            
            therapist_map[data['email']] = therapist.id
            count += 1
            
        except Exception as e:
            print(f"Error migrating therapist {file_path}: {e}")
    
    db.session.commit()
    
    # Save therapist map for client migration
    with open('therapist_map.json', 'w') as f:
        json.dump(therapist_map, f)
    
    return count

def migrate_clients():
    """Migrate patient/client data from JSON files"""
    count = 0
    patients_dir = Path('therapy_data/patients')
    
    if not patients_dir.exists():
        print("No patients directory found")
        return 0
    
    # Load therapist map
    therapist_map = {}
    if os.path.exists('therapist_map.json'):
        with open('therapist_map.json', 'r') as f:
            therapist_map = json.load(f)
    
    # Get default therapist
    default_therapist = Therapist.query.filter_by(license_number='SYSTEM-DEFAULT').first()
    
    client_map = {}  # Map old patient ID to new client ID
    
    for file_path in patients_dir.glob('patient_*.json'):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Extract patient ID from filename
            patient_id = file_path.stem.replace('patient_', '')
            
            # Generate email for client (since old system didn't have client emails)
            client_email = f"patient.{patient_id}@legacy.local"
            
            # Check if already migrated
            if User.query.filter_by(email=client_email).first():
                print(f"Client {patient_id} already exists, skipping...")
                continue
            
            # Create user account
            user = User(
                email=client_email,
                password_hash=bcrypt.generate_password_hash('temp_password_' + patient_id).decode('utf-8'),
                role='client',
                is_active=data.get('status', 'active') == 'active'
            )
            db.session.add(user)
            db.session.flush()
            
            # Find therapist
            therapist_id = None
            if 'enrolledBy' in data and data['enrolledBy'] in therapist_map:
                therapist_id = therapist_map[data['enrolledBy']]
            elif 'therapistEmail' in data and data['therapistEmail'] in therapist_map:
                therapist_id = therapist_map[data['therapistEmail']]
            else:
                therapist_id = default_therapist.id if default_therapist else None
            
            # Create client
            client = Client(
                user_id=user.id,
                client_serial=f"C{patient_id.zfill(8)}",  # Convert old ID to serial format
                therapist_id=therapist_id,
                start_date=datetime.strptime(data.get('enrollmentDate', str(date.today())), '%Y-%m-%d').date()
            )
            db.session.add(client)
            db.session.flush()
            
            # Add tracking plans (default categories)
            default_categories = TrackingCategory.query.filter_by(is_default=True).all()
            for category in default_categories:
                plan = ClientTrackingPlan(
                    client_id=client.id,
                    category_id=category.id
                )
                db.session.add(plan)
            
            # Add enrollment note
            if 'notes' in data or 'additional_notes' in data:
                note_content = data.get('notes', data.get('additional_notes', ''))
                if note_content:
                    note = TherapistNote(
                        client_id=client.id,
                        therapist_id=therapist_id,
                        note_type='migration',
                        content=f"Migrated from legacy system: {note_content}"
                    )
                    db.session.add(note)
            
            client_map[patient_id] = client.id
            count += 1
            
        except Exception as e:
            print(f"Error migrating client {file_path}: {e}")
    
    db.session.commit()
    
    # Save client map for check-in migration
    with open('client_map.json', 'w') as f:
        json.dump(client_map, f)
    
    return count

def migrate_checkins():
    """Migrate check-in data from JSON files"""
    count = 0
    checkins_dir = Path('therapy_data/checkins')
    
    if not checkins_dir.exists():
        print("No checkins directory found")
        return 0
    
    # Load client map
    client_map = {}
    if os.path.exists('client_map.json'):
        with open('client_map.json', 'r') as f:
            client_map = json.load(f)
    
    for patient_dir in checkins_dir.iterdir():
        if not patient_dir.is_dir():
            continue
        
        patient_id = patient_dir.name
        
        # Skip if client not in map
        if patient_id not in client_map:
            print(f"Client {patient_id} not found in map, skipping check-ins...")
            continue
        
        client_id = client_map[patient_id]
        
        for checkin_file in patient_dir.glob('checkin_*.json'):
            try:
                with open(checkin_file, 'r') as f:
                    data = json.load(f)
                
                # Extract date from filename or data
                checkin_date = data.get('date')
                if not checkin_date:
                    # Try to extract from filename
                    checkin_date = checkin_file.stem.replace('checkin_', '')
                
                # Check if already exists
                existing = DailyCheckin.query.filter_by(
                    client_id=client_id,
                    checkin_date=datetime.strptime(checkin_date, '%Y-%m-%d').date()
                ).first()
                
                if existing:
                    continue
                
                # Create check-in
                checkin = DailyCheckin(
                    client_id=client_id,
                    checkin_date=datetime.strptime(checkin_date, '%Y-%m-%d').date(),
                    checkin_time=datetime.strptime(data.get('time', '12:00'), '%H:%M').time(),
                    emotional_value=data.get('emotional', {}).get('value'),
                    emotional_notes=data.get('emotional', {}).get('notes', ''),
                    medication_value=data.get('medication', {}).get('value'),
                    medication_notes=data.get('medication', {}).get('notes', ''),
                    activity_value=data.get('activity', {}).get('value'),
                    activity_notes=data.get('activity', {}).get('notes', '')
                )
                db.session.add(checkin)
                count += 1
                
            except Exception as e:
                print(f"Error migrating check-in {checkin_file}: {e}")
    
    db.session.commit()
    
    # Clean up temporary files
    for temp_file in ['therapist_map.json', 'client_map.json']:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    return count

if __name__ == '__main__':
    print("JSON to PostgreSQL Migration Tool")
    print("=================================")
    print("\nThis will migrate all data from therapy_data/ JSON files to PostgreSQL.")
    print("Make sure your database is configured and running.")
    
    confirm = input("\nProceed with migration? (yes/no): ")
    if confirm.lower() == 'yes':
        migrate_data()
    else:
        print("Migration cancelled.")