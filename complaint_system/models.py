"""
Database Models for Smart Complaint Management System
Defines the structure of all data stored in SQLite
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Initialize SQLAlchemy - this creates the database connection
db = SQLAlchemy()


class User(UserMixin, db.Model):
    """
    User model - represents a person in the system
    UserMixin provides login_user(), logout_user(), etc. from Flask-Login
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Role: 'user' (regular user), 'manager' (complaint handler), 'admin' (system admin)
    role = db.Column(db.String(20), default='user', nullable=False)
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships: a user can have many complaints and many responses
    complaints = db.relationship('Complaint', backref='author', lazy=True, foreign_keys='Complaint.user_id')
    responses = db.relationship('Response', backref='author', lazy=True, foreign_keys='Response.author_id')
    assigned_complaints = db.relationship('Complaint', backref='manager', lazy=True, foreign_keys='Complaint.assigned_to')
    
    def set_password(self, password):
        """Hash a password before storing it - NEVER store plain text passwords!"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify a password by comparing it with the stored hash"""
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        """Flask-Login uses this property to allow/block logins."""
        return self.is_active_user
    
    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class Complaint(db.Model):
    """
    Complaint model - represents a customer complaint/issue
    """
    __tablename__ = 'complaints'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign key: which user submitted this complaint
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Complaint details
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    # AI-predicted category: 'Technical', 'Billing', 'Service', 'General'
    category = db.Column(db.String(50), default='General')
    
    # Priority: 'low', 'medium', 'high' (set by AI based on sentiment + keywords)
    priority = db.Column(db.String(20), default='medium')
    
    # Sentiment analysis result: 'positive', 'neutral', 'negative'
    sentiment = db.Column(db.String(20), default='neutral')
    
    # Status: 'open', 'in_progress', 'resolved', 'closed'
    status = db.Column(db.String(20), default='open')
    
    # AI-suggested response (filled automatically)
    ai_response = db.Column(db.Text, default='')
    
    # Manager's private notes for internal tracking
    internal_notes = db.Column(db.Text, nullable=True)
    
    # Foreign key: which manager is handling this (if any)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # User rating (1-5) if they rate the resolution
    rating = db.Column(db.Integer, nullable=True)
    
    # Relationship: a complaint can have many responses
    responses = db.relationship('Response', backref='complaint', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Complaint #{self.id}: {self.title}>'


class Response(db.Model):
    """
    Response model - represents a manager's response to a complaint
    """
    __tablename__ = 'responses'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Foreign keys
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # The response message
    message = db.Column(db.Text, nullable=False)
    
    # When was this response created
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Response on Complaint #{self.complaint_id}>'
