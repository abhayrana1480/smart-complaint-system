"""
Flask-WTF Forms with Validation
Handles login, registration, and complaint submission forms with built-in security
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from models import User


class LoginForm(FlaskForm):
    """
    Login form with email and password validation
    CSRF protection is automatic with Flask-WTF
    """
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    
    submit = SubmitField('Login')


class RegisterForm(FlaskForm):
    """
    Registration form with password confirmation and unique email checking
    """
    username = StringField('Username', validators=[
        DataRequired(message='Username is required'),
        Length(min=3, max=80, message='Username must be between 3 and 80 characters')
    ])
    
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ])
    
    submit = SubmitField('Create Account')
    
    def validate_email(self, field):
        """
        Custom validator: check if email already exists in database
        Called automatically by WTForms when form is submitted
        """
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered. Please log in instead.')
    
    def validate_username(self, field):
        """
        Custom validator: check if username already exists in database
        """
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken. Choose a different one.')


class ComplaintForm(FlaskForm):
    """
    Form for submitting a new complaint
    Will be used in Phase 5
    """
    title = StringField('Complaint Title', validators=[
        DataRequired(message='Title is required'),
        Length(min=5, max=200, message='Title must be between 5 and 200 characters')
    ])
    
    description = TextAreaField('Describe Your Issue', validators=[
        DataRequired(message='Description is required'),
        Length(min=20, max=5000, message='Description must be between 20 and 5000 characters')
    ])
    
    category = SelectField('Category', choices=[
        ('General', 'General Inquiry'),
        ('Technical', 'Technical Issue'),
        ('Billing', 'Billing Problem'),
        ('Service', 'Service Quality'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    
    submit = SubmitField('Submit Complaint')


class ResponseForm(FlaskForm):
    """
    Form for managers to respond to complaints
    Will be used in Phase 7
    """
    message = TextAreaField('Manager Response (editable AI draft)', validators=[
        DataRequired(message='Response is required'),
        Length(min=10, max=5000, message='Response must be between 10 and 5000 characters')
    ])
    
    status = SelectField('Update Status', choices=[
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ], validators=[DataRequired(message='Status is required')])
    
    internal_notes = TextAreaField('Internal Notes (only visible to managers/admin)', validators=[
        Optional(),
        Length(max=5000, message='Internal notes must be less than 5000 characters')
    ])
    
    submit = SubmitField('Save Update')
