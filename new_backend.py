
"""
Enhanced Therapeutic Companion Backend
With PostgreSQL, Authentication, and Role-Based Access
"""

from flask import Flask, request, jsonify, send_file, session
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from functools import wraps
import os
import secrets
import jwt
from datetime import datetime, timedelta, date
from sqlalchemy import and_, or_, func
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Create Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'postgresql://localhost/therapy_companion'
).replace('postgres://', 'postgresql://')  # Fix for Render
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('PRODUCTION', False)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
CORS(app, supports_credentials=True)

# JWT configuration
JWT_SECRET = app.config['SECRET_KEY']
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# ============= DATABASE MODELS =============

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    therapist = db.relationship('Therapist', backref='user', uselist=False, cascade='all, delete-orphan')
    client = db.relationship('Client', backref='user', uselist=False, cascade='all, delete-orphan')
    session_tokens = db.relationship('SessionToken', backref='user', cascade='all, delete-orphan')

class Therapist(db.Model):
    __tablename__ = 'therapists'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    license_number = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    organization = db.Column(db.String(255))
    specializations = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    clients = db.relationship('Client', backref='therapist', lazy='dynamic')
    notes = db.relationship('TherapistNote', backref='therapist', lazy='dynamic')

class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    client_serial = db.Column(db.String(50), unique=True, nullable=False)
    therapist_id = db.Column(db.Integer, db.ForeignKey('therapists.id'))
    start_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    checkins = db.relationship('DailyCheckin', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    tracking_plans = db.relationship('ClientTrackingPlan', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    goals = db.relationship('WeeklyGoal', backref='client', lazy='dynamic', cascade='all, delete-orphan')
    reminders = db.relationship('Reminder', backref='client', lazy='dynamic', cascade='all, delete-orphan')

class TrackingCategory(db.Model):
    __tablename__ = 'tracking_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    scale_min = db.Column(db.Integer, default=1)
    scale_max = db.Column(db.Integer, default=5)
    is_default = db.Column(db.Boolean, default=False)

class ClientTrackingPlan(db.Model):
    __tablename__ = 'client_tracking_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('tracking_categories.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    category = db.relationship('TrackingCategory', backref='client_plans')

class WeeklyGoal(db.Model):
    __tablename__ = 'weekly_goals'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    therapist_id = db.Column(db.Integer, db.ForeignKey('therapists.id'))
    goal_text = db.Column(db.Text, nullable=False)
    week_start = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    completions = db.relationship('GoalCompletion', backref='goal', lazy='dynamic', cascade='all, delete-orphan')

class DailyCheckin(db.Model):
    __tablename__ = 'daily_checkins'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    checkin_date = db.Column(db.Date, nullable=False)
    checkin_time = db.Column(db.Time, nullable=False)
    emotional_value = db.Column(db.Integer)
    emotional_notes = db.Column(db.Text)
    medication_value = db.Column(db.Integer)
    medication_notes = db.Column(db.Text)
    activity_value = db.Column(db.Integer)
    activity_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('client_id', 'checkin_date'),)

class CategoryResponse(db.Model):
    __tablename__ = 'category_responses'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('tracking_categories.id'))
    response_date = db.Column(db.Date, nullable=False)
    value = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    category = db.relationship('TrackingCategory', backref='responses')

class GoalCompletion(db.Model):
    __tablename__ = 'goal_completions'
    
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('weekly_goals.id'))
    completion_date = db.Column(db.Date, nullable=False)
    completed = db.Column(db.Boolean, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('goal_id', 'completion_date'),)

class Reminder(db.Model):
    __tablename__ = 'reminders'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    reminder_type = db.Column(db.String(50), nullable=False)
    reminder_time = db.Column(db.Time, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_sent = db.Column(db.DateTime)

class Report(db.Model):
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    therapist_id = db.Column(db.Integer, db.ForeignKey('therapists.id'))
    report_type = db.Column(db.String(50), nullable=False)
    week_start = db.Column(db.Date, nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_path = db.Column(db.Text)
    data = db.Column(db.JSON)

class TherapistNote(db.Model):
    __tablename__ = 'therapist_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    therapist_id = db.Column(db.Integer, db.ForeignKey('therapists.id'))
    note_type = db.Column(db.String(50), default='general')
    content = db.Column(db.Text, nullable=False)
    is_mission = db.Column(db.Boolean, default=False)
    mission_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class SessionToken(db.Model):
    __tablename__ = 'session_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    token = db.Column(db.String(255), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============= AUTHENTICATION HELPERS =============

def generate_token(user_id, role):
    """Generate JWT token"""
    payload = {
        'user_id': user_id,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_auth(allowed_roles=None):
    """Authentication decorator"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return jsonify({'error': 'Invalid authorization header'}), 401
            
            token = auth_header.replace('Bearer ', '')
            payload = verify_token(token)
            
            if not payload:
                return jsonify({'error': 'Invalid or expired token'}), 401
            
            # Check if user exists and is active
            user = User.query.get(payload['user_id'])
            if not user or not user.is_active:
                return jsonify({'error': 'User not found or inactive'}), 401
            
            # Check role permissions
            if allowed_roles and user.role not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            # Add user info to request
            request.current_user = user
            request.user_id = user.id
            request.user_role = user.role
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def generate_client_serial():
    """Generate unique client serial number"""
    import random
    import string
    while True:
        serial = 'C' + ''.join(random.choices(string.digits, k=8))
        if not Client.query.filter_by(client_serial=serial).first():
            return serial

# ============= PUBLIC ENDPOINTS =============

@app.route('/')
def index():
    """Serve the main HTML file"""
    return send_file('index.html')

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register new user (therapist or client)"""
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        role = data.get('role')
        
        # Validate input
        if not all([email, password, role]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if role not in ['therapist', 'client']:
            return jsonify({'error': 'Invalid role'}), 400
        
        # Check if email exists
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        # Create user
        user = User(
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode('utf-8'),
            role=role
        )
        db.session.add(user)
        db.session.flush()
        
        # Create role-specific profile
        if role == 'therapist':
            therapist = Therapist(
                user_id=user.id,
                license_number=data.get('license_number', ''),
                name=data.get('name', ''),
                organization=data.get('organization', ''),
                specializations=data.get('specializations', [])
            )
            db.session.add(therapist)
        else:  # client
            client = Client(
                user_id=user.id,
                client_serial=generate_client_serial(),
                therapist_id=data.get('therapist_id'),
                start_date=date.today()
            )
            db.session.add(client)
            
            # Add default tracking categories
            default_categories = TrackingCategory.query.filter_by(is_default=True).all()
            for category in default_categories:
                plan = ClientTrackingPlan(
                    client_id=client.id,
                    category_id=category.id
                )
                db.session.add(plan)
        
        db.session.commit()
        
        # Generate token
        token = generate_token(user.id, role)
        
        return jsonify({
            'success': True,
            'token': token,
            'user': {
                'id': user.id,
                'email': user.email,
                'role': user.role
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user"""
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not all([email, password]):
            return jsonify({'error': 'Missing email or password'}), 400
        
        # Find user
        user = User.query.filter_by(email=email).first()
        if not user or not bcrypt.check_password_hash(user.password_hash, password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account deactivated'}), 401
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Generate token
        token = generate_token(user.id, user.role)
        
        # Get role-specific data
        response_data = {
            'success': True,
            'token': token,
            'user': {
                'id': user.id,
                'email': user.email,
                'role': user.role
            }
        }
        
        if user.role == 'therapist' and user.therapist:
            response_data['therapist'] = {
                'id': user.therapist.id,
                'name': user.therapist.name,
                'license_number': user.therapist.license_number,
                'organization': user.therapist.organization
            }
        elif user.role == 'client' and user.client:
            response_data['client'] = {
                'id': user.client.id,
                'serial': user.client.client_serial,
                'start_date': user.client.start_date.isoformat()
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= THERAPIST ENDPOINTS =============

@app.route('/api/therapist/dashboard', methods=['GET'])
@require_auth(['therapist'])
def therapist_dashboard():
    """Get therapist dashboard data"""
    try:
        therapist = request.current_user.therapist
        
        # Get client statistics
        total_clients = therapist.clients.count()
        active_clients = therapist.clients.filter_by(is_active=True).count()
        
        # Get recent activity
        recent_checkins = db.session.query(DailyCheckin).join(Client).filter(
            Client.therapist_id == therapist.id,
            DailyCheckin.checkin_date >= date.today() - timedelta(days=7)
        ).count()
        
        # Get pending missions
        pending_missions = TherapistNote.query.filter_by(
            therapist_id=therapist.id,
            is_mission=True,
            mission_completed=False
        ).count()
        
        return jsonify({
            'success': True,
            'therapist': {
                'name': therapist.name,
                'license_number': therapist.license_number,
                'organization': therapist.organization
            },
            'statistics': {
                'total_clients': total_clients,
                'active_clients': active_clients,
                'recent_checkins': recent_checkins,
                'pending_missions': pending_missions
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/therapist/clients', methods=['GET'])
@require_auth(['therapist'])
def get_therapist_clients():
    """Get list of therapist's clients"""
    try:
        therapist = request.current_user.therapist
        
        # Get filter parameters
        status = request.args.get('status', 'all')
        sort_by = request.args.get('sort_by', 'start_date')
        
        # Build query
        query = therapist.clients
        
        if status == 'active':
            query = query.filter_by(is_active=True)
        elif status == 'inactive':
            query = query.filter_by(is_active=False)
        
        # Sort
        if sort_by == 'start_date':
            query = query.order_by(Client.start_date.desc())
        elif sort_by == 'serial':
            query = query.order_by(Client.client_serial)
        
        clients = query.all()
        
        # Build response
        client_data = []
        for client in clients:
            # Get last check-in
            last_checkin = client.checkins.order_by(DailyCheckin.checkin_date.desc()).first()
            
            # Get completion rate for last week
            week_start = date.today() - timedelta(days=date.today().weekday())
            week_checkins = client.checkins.filter(
                DailyCheckin.checkin_date >= week_start
            ).count()
            
            client_data.append({
                'id': client.id,
                'serial': client.client_serial,
                'start_date': client.start_date.isoformat(),
                'is_active': client.is_active,
                'last_checkin': last_checkin.checkin_date.isoformat() if last_checkin else None,
                'week_completion': f"{week_checkins}/7",
                'tracking_categories': [
                    plan.category.name for plan in client.tracking_plans.filter_by(is_active=True)
                ]
            })
        
        return jsonify({
            'success': True,
            'clients': client_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/therapist/client/<int:client_id>', methods=['GET'])
@require_auth(['therapist'])
def get_client_details(client_id):
    """Get detailed client information"""
    try:
        therapist = request.current_user.therapist
        
        # Verify client belongs to therapist
        client = Client.query.filter_by(
            id=client_id,
            therapist_id=therapist.id
        ).first()
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Get tracking plans
        tracking_plans = []
        for plan in client.tracking_plans.filter_by(is_active=True):
            tracking_plans.append({
                'id': plan.id,
                'category': plan.category.name,
                'description': plan.category.description
            })
        
        # Get active goals
        active_goals = []
        week_start = date.today() - timedelta(days=date.today().weekday())
        for goal in client.goals.filter_by(
            week_start=week_start,
            is_active=True
        ):
            # Get completions for this week
            completions = {}
            for i in range(7):
                day = week_start + timedelta(days=i)
                completion = goal.completions.filter_by(completion_date=day).first()
                completions[day.isoformat()] = completion.completed if completion else None
            
            active_goals.append({
                'id': goal.id,
                'text': goal.goal_text,
                'completions': completions
            })
        
        # Get recent check-ins
        recent_checkins = []
        for checkin in client.checkins.order_by(
            DailyCheckin.checkin_date.desc()
        ).limit(7):
            recent_checkins.append({
                'date': checkin.checkin_date.isoformat(),
                'emotional': checkin.emotional_value,
                'medication': checkin.medication_value,
                'activity': checkin.activity_value
            })
        
        # Get therapist notes/missions
        notes = []
        for note in TherapistNote.query.filter_by(
            client_id=client_id,
            therapist_id=therapist.id
        ).order_by(TherapistNote.created_at.desc()).limit(10):
            notes.append({
                'id': note.id,
                'type': note.note_type,
                'content': note.content,
                'is_mission': note.is_mission,
                'completed': note.mission_completed,
                'created_at': note.created_at.isoformat()
            })
        
        return jsonify({
            'success': True,
            'client': {
                'id': client.id,
                'serial': client.client_serial,
                'start_date': client.start_date.isoformat(),
                'is_active': client.is_active,
                'tracking_plans': tracking_plans,
                'active_goals': active_goals,
                'recent_checkins': recent_checkins,
                'notes': notes
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/therapist/create-client', methods=['POST'])
@require_auth(['therapist'])
def create_client():
    """Create new client"""
    try:
        therapist = request.current_user.therapist
        data = request.json
        
        # Create user account for client
        email = data.get('email')
        password = data.get('password', secrets.token_urlsafe(8))
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        # Create user
        user = User(
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode('utf-8'),
            role='client'
        )
        db.session.add(user)
        db.session.flush()
        
        # Create client
        client = Client(
            user_id=user.id,
            client_serial=generate_client_serial(),
            therapist_id=therapist.id,
            start_date=date.today()
        )
        db.session.add(client)
        db.session.flush()
        
        # Add tracking categories
        category_ids = data.get('tracking_categories', [])
        if not category_ids:
            # Add default categories
            default_categories = TrackingCategory.query.filter_by(is_default=True).all()
            category_ids = [cat.id for cat in default_categories]
        
        for cat_id in category_ids:
            plan = ClientTrackingPlan(
                client_id=client.id,
                category_id=cat_id
            )
            db.session.add(plan)
        
        # Add initial goals if provided
        goals = data.get('initial_goals', [])
        week_start = date.today() - timedelta(days=date.today().weekday())
        for goal_text in goals:
            goal = WeeklyGoal(
                client_id=client.id,
                therapist_id=therapist.id,
                goal_text=goal_text,
                week_start=week_start
            )
            db.session.add(goal)
        
        # Add welcome note
        welcome_note = TherapistNote(
            client_id=client.id,
            therapist_id=therapist.id,
            note_type='welcome',
            content=f"Welcome to therapy! Your journey begins today. Your temporary password is: {password}"
        )
        db.session.add(welcome_note)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'client': {
                'id': client.id,
                'serial': client.client_serial,
                'email': email,
                'temporary_password': password
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/therapist/add-goal', methods=['POST'])
@require_auth(['therapist'])
def add_weekly_goal():
    """Add weekly goal for client"""
    try:
        therapist = request.current_user.therapist
        data = request.json
        
        client_id = data.get('client_id')
        goal_text = data.get('goal_text')
        week_start_str = data.get('week_start')
        
        # Verify client belongs to therapist
        client = Client.query.filter_by(
            id=client_id,
            therapist_id=therapist.id
        ).first()
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Parse week start
        if week_start_str:
            week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
        else:
            # Default to current week
            week_start = date.today() - timedelta(days=date.today().weekday())
        
        # Create goal
        goal = WeeklyGoal(
            client_id=client_id,
            therapist_id=therapist.id,
            goal_text=goal_text,
            week_start=week_start
        )
        db.session.add(goal)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'goal': {
                'id': goal.id,
                'text': goal.goal_text,
                'week_start': goal.week_start.isoformat()
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/therapist/add-note', methods=['POST'])
@require_auth(['therapist'])
def add_therapist_note():
    """Add note or mission for client"""
    try:
        therapist = request.current_user.therapist
        data = request.json
        
        client_id = data.get('client_id')
        content = data.get('content')
        is_mission = data.get('is_mission', False)
        note_type = data.get('note_type', 'general')
        
        # Verify client belongs to therapist
        client = Client.query.filter_by(
            id=client_id,
            therapist_id=therapist.id
        ).first()
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Create note
        note = TherapistNote(
            client_id=client_id,
            therapist_id=therapist.id,
            content=content,
            is_mission=is_mission,
            note_type=note_type
        )
        db.session.add(note)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'note': {
                'id': note.id,
                'content': note.content,
                'is_mission': note.is_mission,
                'created_at': note.created_at.isoformat()
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============= CLIENT ENDPOINTS =============

@app.route('/api/client/dashboard', methods=['GET'])
@require_auth(['client'])
def client_dashboard():
    """Get client dashboard data"""
    try:
        client = request.current_user.client
        
        # Get today's check-in status
        today_checkin = client.checkins.filter_by(checkin_date=date.today()).first()
        
        # Get active tracking categories
        tracking_categories = []
        for plan in client.tracking_plans.filter_by(is_active=True):
            # Get today's response
            today_response = CategoryResponse.query.filter_by(
                client_id=client.id,
                category_id=plan.category_id,
                response_date=date.today()
            ).first()
            
            tracking_categories.append({
                'id': plan.category_id,
                'name': plan.category.name,
                'description': plan.category.description,
                'today_value': today_response.value if today_response else None
            })
        
        # Get this week's goals
        week_start = date.today() - timedelta(days=date.today().weekday())
        weekly_goals = []
        for goal in client.goals.filter_by(
            week_start=week_start,
            is_active=True
        ):
            # Get today's completion
            today_completion = goal.completions.filter_by(
                completion_date=date.today()
            ).first()
            
            weekly_goals.append({
                'id': goal.id,
                'text': goal.goal_text,
                'today_completed': today_completion.completed if today_completion else None
            })
        
        # Get reminders
        reminders = []
        for reminder in client.reminders.filter_by(is_active=True):
            reminders.append({
                'type': reminder.reminder_type,
                'time': reminder.reminder_time.strftime('%H:%M')
            })
        
        return jsonify({
            'success': True,
            'client': {
                'serial': client.client_serial,
                'start_date': client.start_date.isoformat()
            },
            'today': {
                'has_checkin': today_checkin is not None,
                'date': date.today().isoformat()
            },
            'tracking_categories': tracking_categories,
            'weekly_goals': weekly_goals,
            'reminders': reminders
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/client/checkin', methods=['POST'])
@require_auth(['client'])
def submit_checkin():
    """Submit daily check-in"""
    try:
        client = request.current_user.client
        data = request.json
        
        checkin_date = data.get('date', date.today().isoformat())
        checkin_date = datetime.strptime(checkin_date, '%Y-%m-%d').date()
        
        # Check if check-in exists
        existing = client.checkins.filter_by(checkin_date=checkin_date).first()
        
        if existing:
            # Update existing
            existing.checkin_time = datetime.now().time()
            existing.emotional_value = data.get('emotional_value')
            existing.emotional_notes = data.get('emotional_notes')
            existing.medication_value = data.get('medication_value')
            existing.medication_notes = data.get('medication_notes')
            existing.activity_value = data.get('activity_value')
            existing.activity_notes = data.get('activity_notes')
        else:
            # Create new
            checkin = DailyCheckin(
                client_id=client.id,
                checkin_date=checkin_date,
                checkin_time=datetime.now().time(),
                emotional_value=data.get('emotional_value'),
                emotional_notes=data.get('emotional_notes'),
                medication_value=data.get('medication_value'),
                medication_notes=data.get('medication_notes'),
                activity_value=data.get('activity_value'),
                activity_notes=data.get('activity_notes')
            )
            db.session.add(checkin)
        
        # Save category responses
        category_responses = data.get('category_responses', {})
        for cat_id, value in category_responses.items():
            # Check if response exists
            existing_response = CategoryResponse.query.filter_by(
                client_id=client.id,
                category_id=int(cat_id),
                response_date=checkin_date
            ).first()
            
            if existing_response:
                existing_response.value = value
            else:
                response = CategoryResponse(
                    client_id=client.id,
                    category_id=int(cat_id),
                    response_date=checkin_date,
                    value=value
                )
                db.session.add(response)
        
        # Save goal completions
        goal_completions = data.get('goal_completions', {})
        for goal_id, completed in goal_completions.items():
            # Check if completion exists
            existing_completion = GoalCompletion.query.filter_by(
                goal_id=int(goal_id),
                completion_date=checkin_date
            ).first()
            
            if existing_completion:
                existing_completion.completed = completed
            else:
                completion = GoalCompletion(
                    goal_id=int(goal_id),
                    completion_date=checkin_date,
                    completed=completed
                )
                db.session.add(completion)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Check-in saved successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/client/progress', methods=['GET'])
@require_auth(['client'])
def get_client_progress():
    """Get client's progress data"""
    try:
        client = request.current_user.client
        
        # Get date range
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        # Get check-ins
        checkins = client.checkins.filter(
            DailyCheckin.checkin_date.between(start_date, end_date)
        ).order_by(DailyCheckin.checkin_date).all()
        
        checkin_data = []
        for checkin in checkins:
            checkin_data.append({
                'date': checkin.checkin_date.isoformat(),
                'emotional': checkin.emotional_value,
                'medication': checkin.medication_value,
                'activity': checkin.activity_value
            })
        
        # Get category responses
        category_data = {}
        for plan in client.tracking_plans.filter_by(is_active=True):
            responses = CategoryResponse.query.filter(
                CategoryResponse.client_id == client.id,
                CategoryResponse.category_id == plan.category_id,
                CategoryResponse.response_date.between(start_date, end_date)
            ).order_by(CategoryResponse.response_date).all()
            
            category_data[plan.category.name] = [
                {
                    'date': resp.response_date.isoformat(),
                    'value': resp.value
                } for resp in responses
            ]
        
        return jsonify({
            'success': True,
            'progress': {
                'checkins': checkin_data,
                'categories': category_data
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= REPORT GENERATION =============

@app.route('/api/reports/generate/<int:client_id>/<week>', methods=['GET'])
@require_auth(['therapist'])
def generate_report(client_id, week):
    """Generate weekly report"""
    try:
        therapist = request.current_user.therapist
        
        # Verify client belongs to therapist
        client = Client.query.filter_by(
            id=client_id,
            therapist_id=therapist.id
        ).first()
        
        if not client:
            return jsonify({'error': 'Client not found'}), 404
        
        # Parse week
        year, week_num = week.split('-W')
        year = int(year)
        week_num = int(week_num)
        
        # Calculate week dates
        jan1 = datetime(year, 1, 1)
        days_to_monday = (7 - jan1.weekday()) % 7
        if days_to_monday == 0:
            days_to_monday = 7
        first_monday = jan1 + timedelta(days=days_to_monday - 7)
        week_start = first_monday + timedelta(weeks=week_num)
        
        # Create Excel report (similar to original implementation)
        # ... (Excel generation code here)
        
        # For now, return summary data
        week_data = {}
        for i in range(7):
            day = week_start + timedelta(days=i)
            checkin = client.checkins.filter_by(checkin_date=day).first()
            if checkin:
                week_data[day.isoformat()] = {
                    'emotional': checkin.emotional_value,
                    'medication': checkin.medication_value,
                    'activity': checkin.activity_value
                }
        
        return jsonify({
            'success': True,
            'week_data': week_data,
            'client_serial': client.client_serial
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= HEALTH CHECK =============

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })

# ============= INITIALIZATION =============

# Flag to ensure single initialization
_initialized = False

def initialize_database():
    """Initialize database with default data"""
    global _initialized
    if _initialized:
        return
    
    _initialized = True
    db.create_all()
    
    # Add default tracking categories if not exist
    if TrackingCategory.query.count() == 0:
        default_categories = [
            ('Emotion Level', 'Overall emotional state', True),
            ('Energy', 'Physical and mental energy levels', True),
            ('Social Activity', 'Engagement in social interactions', True),
            ('Sleep Quality', 'Quality of sleep', False),
            ('Anxiety Level', 'Level of anxiety experienced', False),
            ('Motivation', 'Level of motivation and drive', False)
        ]
        
        for name, description, is_default in default_categories:
            category = TrackingCategory(
                name=name,
                description=description,
                is_default=is_default
            )
            db.session.add(category)
        
        db.session.commit()
        print("Database initialized with default tracking categories")

# Initialize on first request (replaces @app.before_first_request)
@app.before_request
def before_request():
    initialize_database()

# Don't initialize on import for production
# Let init_db.py handle it during deployment
if not os.environ.get('PRODUCTION'):
    with app.app_context():
        initialize_database()

if __name__ == '__main__':
    # Ensure database is created when running directly
    with app.app_context():
        db.create_all()
        initialize_database()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=not os.environ.get('PRODUCTION'))
