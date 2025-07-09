-- PostgreSQL Schema for Therapeutic Companion System

-- Users table (for authentication)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('therapist', 'client', 'admin')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Therapists table
CREATE TABLE therapists (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    license_number VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    organization VARCHAR(255),
    specializations TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Clients table
CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    client_serial VARCHAR(50) UNIQUE NOT NULL, -- Anonymous identifier
    therapist_id INTEGER REFERENCES therapists(id),
    start_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tracking categories (emotion, energy, social activity, etc.)
CREATE TABLE tracking_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    scale_min INTEGER DEFAULT 1,
    scale_max INTEGER DEFAULT 5,
    is_default BOOLEAN DEFAULT FALSE
);

-- Client tracking plans (which categories each client tracks)
CREATE TABLE client_tracking_plans (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES tracking_categories(id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Weekly goals/tasks
CREATE TABLE weekly_goals (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    therapist_id INTEGER REFERENCES therapists(id),
    goal_text TEXT NOT NULL,
    week_start DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily check-ins
CREATE TABLE daily_checkins (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    checkin_date DATE NOT NULL,
    checkin_time TIME NOT NULL,
    emotional_value INTEGER CHECK (emotional_value BETWEEN 1 AND 5),
    emotional_notes TEXT,
    medication_value INTEGER CHECK (medication_value IN (0, 1, 3, 5)),
    medication_notes TEXT,
    activity_value INTEGER CHECK (activity_value BETWEEN 1 AND 5),
    activity_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(client_id, checkin_date)
);

-- Category tracking responses
CREATE TABLE category_responses (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES tracking_categories(id),
    response_date DATE NOT NULL,
    value INTEGER NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Goal completions
CREATE TABLE goal_completions (
    id SERIAL PRIMARY KEY,
    goal_id INTEGER REFERENCES weekly_goals(id) ON DELETE CASCADE,
    completion_date DATE NOT NULL,
    completed BOOLEAN NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(goal_id, completion_date)
);

-- Reminders
CREATE TABLE reminders (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    reminder_type VARCHAR(50) NOT NULL,
    reminder_time TIME NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_sent TIMESTAMP
);

-- Reports
CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    therapist_id INTEGER REFERENCES therapists(id),
    report_type VARCHAR(50) NOT NULL,
    week_start DATE NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT,
    data JSONB
);

-- Therapist notes/missions
CREATE TABLE therapist_notes (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    therapist_id INTEGER REFERENCES therapists(id),
    note_type VARCHAR(50) DEFAULT 'general',
    content TEXT NOT NULL,
    is_mission BOOLEAN DEFAULT FALSE,
    mission_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Session tokens for authentication
CREATE TABLE session_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_clients_therapist ON clients(therapist_id);
CREATE INDEX idx_checkins_client_date ON daily_checkins(client_id, checkin_date);
CREATE INDEX idx_category_responses_client ON category_responses(client_id, response_date);
CREATE INDEX idx_reports_client ON reports(client_id, week_start);
CREATE INDEX idx_session_tokens_user ON session_tokens(user_id);
CREATE INDEX idx_session_tokens_token ON session_tokens(token);

-- Insert default tracking categories
INSERT INTO tracking_categories (name, description, is_default) VALUES
('Emotion Level', 'Overall emotional state', TRUE),
('Energy', 'Physical and mental energy levels', TRUE),
('Social Activity', 'Engagement in social interactions', TRUE),
('Sleep Quality', 'Quality of sleep', FALSE),
('Anxiety Level', 'Level of anxiety experienced', FALSE),
('Motivation', 'Level of motivation and drive', FALSE);