"""
Smart Complaint Management System - Main Flask Application
A simple, college-friendly complaint management system with AI classification and sentiment analysis
"""

from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Complaint, Response
from forms import LoginForm, RegisterForm, ComplaintForm, ResponseForm
from ai_module import process_complaint_with_ai, get_chatbot_response
from datetime import datetime
import os
from sqlalchemy import case, inspect, text

# Initialize Flask app with templates folder in current directory
app = Flask(__name__, template_folder='.')

# ─── CONFIGURATION ───────────────────────────────────────────────
# Secret key for session management (change this in production!)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'

# Database configuration - SQLite file in the same folder
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "complaints.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)

# Initialize Flask-Login (handles user sessions)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to login if not authenticated

@login_manager.user_loader
def load_user(user_id):
    """Flask-Login calls this to get the current user from the session"""
    return User.query.get(int(user_id))


# ─── DATABASE INITIALIZATION ────────────────────────────────────
def init_db():
    """
    Create all database tables if they don't exist
    Called once when the app starts
    """
    with app.app_context():
        db.create_all()
        migrate_db_schema()
        print("✅ Database tables created!")


def migrate_db_schema():
    """
    Apply tiny schema updates for existing SQLite files without full migration tooling.
    This keeps the college project simple and avoids manual database reset.
    """
    inspector = inspect(db.engine)
    user_columns = {column['name'] for column in inspector.get_columns('users')}
    complaint_columns = {column['name'] for column in inspector.get_columns('complaints')}

    if 'is_active_user' not in user_columns:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE users ADD COLUMN is_active_user BOOLEAN DEFAULT 1'))
            connection.execute(text('UPDATE users SET is_active_user = 1 WHERE is_active_user IS NULL'))
        print("✅ Added missing column: users.is_active_user")

    if 'internal_notes' not in complaint_columns:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE complaints ADD COLUMN internal_notes TEXT'))
        print("✅ Added missing column: complaints.internal_notes")


def seed_db():
    """
    Populate database with test accounts so you can log in immediately
    Only runs if the database is empty
    """
    with app.app_context():
        # Check if we already have data
        if User.query.first() is not None:
            print("📊 Database already has data. Skipping seed.")
            return
        
        print("🌱 Seeding database with test accounts...")
        
        # Create Admin user
        admin = User(
            username='admin',
            email='admin@college.com',
            role='admin'
        )
        admin.set_password('admin123')
        db.session.add(admin)
        
        # Create Manager users
        manager1 = User(
            username='manager1',
            email='manager1@college.com',
            role='manager'
        )
        manager1.set_password('manager123')
        db.session.add(manager1)
        
        manager2 = User(
            username='manager2',
            email='manager2@college.com',
            role='manager'
        )
        manager2.set_password('manager123')
        db.session.add(manager2)
        
        # Create Regular user
        user = User(
            username='user',
            email='user@college.com',
            role='user'
        )
        user.set_password('user123')
        db.session.add(user)
        
        # Commit all users to database
        db.session.commit()
        
        print("✅ Seed data created!")
        print("\n📝 Test Accounts:")
        print("  Admin: admin@college.com / admin123")
        print("  Manager 1: manager1@college.com / manager123")
        print("  Manager 2: manager2@college.com / manager123")
        print("  User: user@college.com / user123\n")


# ─── ROUTES ─────────────────────────────────────────────────────

def assign_manager_to_complaint():
    """
    Pick a manager for a new complaint.
    For simplicity, this assigns the manager with the least currently open/in-progress complaints.
    """
    managers = User.query.filter_by(role='manager', is_active_user=True).all()
    if not managers:
        return None

    chosen_manager = None
    lowest_load = None

    for manager in managers:
        active_count = Complaint.query.filter(
            Complaint.assigned_to == manager.id,
            Complaint.status.in_(['open', 'in_progress'])
        ).count()

        if lowest_load is None or active_count < lowest_load:
            lowest_load = active_count
            chosen_manager = manager

    return chosen_manager

@app.route('/')
def index():
    """Home page - redirect to login if not authenticated, else to dashboard"""
    if current_user.is_authenticated:
        # Redirect based on role
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'manager':
            return redirect(url_for('manager_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Registration page with form validation and CSRF protection
    Uses Flask-WTF to validate inputs before saving to database
    """
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    
    # Check if form was submitted AND all validation passed
    if form.validate_on_submit():
        # Create new user with validated data
        new_user = User(username=form.username.data, email=form.email.data, role='user')
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        
        flash('✅ Registration successful! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    # If form has errors, they're automatically shown in the template
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page with form validation and CSRF protection
    Uses Flask-WTF to validate email/password before authenticating
    """
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    
    # Check if form was submitted AND all validation passed
    if form.validate_on_submit():
        # Find user by email
        user = User.query.filter_by(email=form.email.data).first()
        
        # Verify user exists and password is correct
        if user and user.check_password(form.password.data):
            if not user.is_active_user:
                flash('❌ Your account is deactivated. Please contact admin.', 'error')
                return redirect(url_for('login'))
            login_user(user, remember=True)  # remember=True keeps user logged in
            
            # Redirect based on role
            if user.role == 'admin':
                flash(f'✅ Welcome Admin {user.username}!', 'success')
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'manager':
                flash(f'✅ Welcome Manager {user.username}!', 'success')
                return redirect(url_for('manager_dashboard'))
            else:
                flash(f'✅ Welcome {user.username}!', 'success')
                return redirect(url_for('user_dashboard'))
        else:
            flash('❌ Invalid email or password. Please try again.', 'error')
    
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    """Logout - clear user session"""
    logout_user()
    flash('✅ Logged out successfully!', 'success')
    return redirect(url_for('login'))


# ─── USER ROUTES (Phase 5) ───────────────────────────────────────

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    """
    User dashboard showing quick stats and recent complaints.
    This gives users a simple overview of their complaint activity.
    """
    if current_user.role != 'user':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    user_complaints = Complaint.query.filter_by(user_id=current_user.id)

    open_count = user_complaints.filter_by(status='open').count()
    in_progress_count = user_complaints.filter_by(status='in_progress').count()
    resolved_count = user_complaints.filter_by(status='resolved').count()

    recent_complaints = Complaint.query.filter_by(user_id=current_user.id).order_by(
        Complaint.created_at.desc()
    ).limit(5).all()

    return render_template(
        'user_dashboard.html',
        open_count=open_count,
        in_progress_count=in_progress_count,
        resolved_count=resolved_count,
        recent_complaints=recent_complaints
    )


@app.route('/user/submit', methods=['GET', 'POST'])
@login_required
def submit_complaint():
    """
    Complaint submission page for users.
    On submit, AI automatically predicts category, sentiment, priority, and a suggested response.
    """
    if current_user.role != 'user':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    form = ComplaintForm()

    if form.validate_on_submit():
        ai_result = process_complaint_with_ai(
            title=form.title.data,
            description=form.description.data
        )

        assigned_manager = assign_manager_to_complaint()

        complaint = Complaint(
            user_id=current_user.id,
            title=form.title.data,
            description=form.description.data,
            category=ai_result['category'],
            priority=ai_result['priority'],
            sentiment=ai_result['sentiment'],
            status='open',
            ai_response=ai_result['ai_response'],
            assigned_to=assigned_manager.id if assigned_manager else None
        )

        db.session.add(complaint)
        db.session.commit()

        flash(
            f"✅ Your complaint has been classified as {ai_result['category']}, priority: {ai_result['priority']}.",
            'success'
        )
        return redirect(url_for('my_complaints'))

    return render_template('user_submit.html', form=form)


@app.route('/user/complaints')
@login_required
def my_complaints():
    """
    List all complaints submitted by the logged-in user.
    The list includes status, category, priority, sentiment, and assigned manager.
    """
    if current_user.role != 'user':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    complaints = Complaint.query.filter_by(user_id=current_user.id).order_by(
        Complaint.created_at.desc()
    ).all()

    return render_template('my_complaints.html', complaints=complaints)


@app.route('/user/complaint/<int:complaint_id>')
@login_required
def view_complaint(complaint_id):
    """
    Detail page for a single complaint.
    Shows full complaint text, status timeline, manager responses, and rating option.
    """
    complaint = Complaint.query.get_or_404(complaint_id)
    
    # Ensure user can only view their own complaints
    if complaint.user_id != current_user.id:
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('my_complaints'))
    
    return render_template('complaint_detail.html', complaint=complaint)


@app.route('/user/complaint/<int:complaint_id>/rate', methods=['POST'])
@login_required
def rate_complaint(complaint_id):
    """
    Allow user to rate a resolved complaint (1-5 stars).
    """
    complaint = Complaint.query.get_or_404(complaint_id)
    
    # Ensure user can only rate their own complaints
    if complaint.user_id != current_user.id:
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('my_complaints'))
    
    # Only allow rating if complaint is resolved
    if complaint.status != 'resolved':
        flash('❌ You can only rate resolved complaints.', 'error')
        return redirect(url_for('view_complaint', complaint_id=complaint_id))
    
    # Get rating from request
    rating = request.form.get('rating', type=int)
    if rating not in [1, 2, 3, 4, 5]:
        flash('❌ Invalid rating. Please select 1-5 stars.', 'error')
        return redirect(url_for('view_complaint', complaint_id=complaint_id))
    
    complaint.rating = rating
    db.session.commit()
    
    flash(f'⭐ Thank you! You rated this complaint {rating}/5 stars.', 'success')
    return redirect(url_for('view_complaint', complaint_id=complaint_id))


# ─── MANAGER ROUTES (placeholder for now) ───────────────────────

@app.route('/manager/dashboard')
@login_required
def manager_dashboard():
    """
    Manager dashboard showing assigned complaints sorted by priority.
    Includes category, priority, sentiment emoji, SLA days, and quick action.
    """
    if current_user.role != 'manager':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    priority_order = case(
        (Complaint.priority == 'high', 1),
        (Complaint.priority == 'medium', 2),
        (Complaint.priority == 'low', 3),
        else_=4
    )

    assigned_complaints = Complaint.query.filter_by(assigned_to=current_user.id).order_by(
        priority_order,
        Complaint.created_at.asc()
    ).all()

    return render_template(
        'manager_dashboard.html',
        complaints=assigned_complaints,
        now=datetime.utcnow()
    )


@app.route('/manager/complaint/<int:complaint_id>', methods=['GET', 'POST'])
@login_required
def manager_complaint(complaint_id):
    """
    Manager complaint detail page.
    Allows manager to edit AI response draft, write internal notes, and update status.
    """
    if current_user.role != 'manager':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    complaint = Complaint.query.get_or_404(complaint_id)

    if complaint.assigned_to != current_user.id:
        flash('❌ This complaint is not assigned to you.', 'error')
        return redirect(url_for('manager_dashboard'))

    form = ResponseForm()

    if request.method == 'GET':
        form.message.data = complaint.ai_response or ''
        form.status.data = complaint.status
        form.internal_notes.data = complaint.internal_notes or ''

    if form.validate_on_submit():
        response = Response(
            complaint_id=complaint.id,
            author_id=current_user.id,
            message=form.message.data.strip()
        )

        complaint.status = form.status.data
        complaint.internal_notes = form.internal_notes.data.strip() if form.internal_notes.data else None

        if complaint.status == 'resolved' and complaint.resolved_at is None:
            complaint.resolved_at = datetime.utcnow()
        elif complaint.status in ['open', 'in_progress']:
            complaint.resolved_at = None

        db.session.add(response)
        db.session.commit()

        flash('✅ Complaint update saved successfully.', 'success')
        return redirect(url_for('manager_complaint', complaint_id=complaint.id))

    return render_template('manager_complaint.html', complaint=complaint, form=form)


# ─── ADMIN ROUTES (placeholder for now) ─────────────────────────

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """
    Admin dashboard with system-wide stats, charts, and recent activity.
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    total_complaints = Complaint.query.count()
    open_complaints = Complaint.query.filter(Complaint.status.in_(['open', 'in_progress'])).count()
    resolved_complaints = Complaint.query.filter_by(status='resolved').count()

    resolved_items = Complaint.query.filter(
        Complaint.status == 'resolved',
        Complaint.resolved_at.isnot(None)
    ).all()
    avg_resolution_days = 0
    if resolved_items:
        total_days = sum((item.resolved_at - item.created_at).days for item in resolved_items)
        avg_resolution_days = round(total_days / len(resolved_items), 2)

    category_rows = db.session.query(
        Complaint.category, db.func.count(Complaint.id)
    ).group_by(Complaint.category).all()
    category_labels = [row[0] for row in category_rows]
    category_counts = [row[1] for row in category_rows]

    status_rows = db.session.query(
        Complaint.status, db.func.count(Complaint.id)
    ).group_by(Complaint.status).all()
    status_labels = [row[0].replace('_', ' ').title() for row in status_rows]
    status_counts = [row[1] for row in status_rows]

    recent_activity = []

    recent_complaints = Complaint.query.order_by(Complaint.created_at.desc()).limit(10).all()
    for complaint in recent_complaints:
        recent_activity.append({
            'time': complaint.created_at,
            'text': f"Complaint #{complaint.id} submitted by {complaint.author.username}"
        })

    recent_responses = Response.query.order_by(Response.created_at.desc()).limit(10).all()
    for response in recent_responses:
        recent_activity.append({
            'time': response.created_at,
            'text': f"{response.author.username} replied on Complaint #{response.complaint_id}"
        })

    recent_activity = sorted(recent_activity, key=lambda item: item['time'], reverse=True)[:10]

    return render_template(
        'admin_dashboard.html',
        total_complaints=total_complaints,
        open_complaints=open_complaints,
        resolved_complaints=resolved_complaints,
        avg_resolution_days=avg_resolution_days,
        category_labels=category_labels,
        category_counts=category_counts,
        status_labels=status_labels,
        status_counts=status_counts,
        recent_activity=recent_activity
    )


@app.route('/admin/users')
@login_required
def admin_users():
    """
    Admin user management page: view users, update role, deactivate user.
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/users/create-manager', methods=['POST'])
@login_required
def create_manager_account():
    """
    Create a new manager account from the admin users page.
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    if not username or not email or not password:
        flash('❌ All fields are required.', 'error')
        return redirect(url_for('admin_users'))

    if len(password) < 6:
        flash('❌ Password must be at least 6 characters.', 'error')
        return redirect(url_for('admin_users'))

    if User.query.filter_by(email=email).first():
        flash('❌ Email already exists.', 'error')
        return redirect(url_for('admin_users'))

    if User.query.filter_by(username=username).first():
        flash('❌ Username already exists.', 'error')
        return redirect(url_for('admin_users'))

    # Create the new manager account
    from werkzeug.security import generate_password_hash
    new_manager = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role='manager'
    )
    db.session.add(new_manager)
    db.session.commit()

    flash(f'✅ Manager account created: {username} ({email})', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/role', methods=['POST'])
@login_required
def update_user_role(user_id):
    """
    Update a user's role from admin users page.
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role', '').strip()

    if new_role not in ['user', 'manager', 'admin']:
        flash('❌ Invalid role selected.', 'error')
        return redirect(url_for('admin_users'))

    user.role = new_role
    db.session.commit()
    flash(f'✅ Role updated for {user.username} to {new_role}.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/deactivate', methods=['POST'])
@login_required
def deactivate_user(user_id):
    """
    Deactivate a user account (cannot deactivate self admin).
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('❌ You cannot deactivate your own admin account.', 'error')
        return redirect(url_for('admin_users'))

    user.is_active_user = False
    db.session.commit()
    flash(f'✅ {user.username} has been deactivated.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/api/chat', methods=['POST'])
@app.route('/api/chatbot', methods=['POST'])
@login_required
def chatbot_api():
    """
    API endpoint for FAQ chatbot messages.
    This returns JSON in the format: {"response": "..."}.
    """
    if current_user.role != 'user':
        return {'response': 'Only users can access this chatbot.'}, 403

    data = request.get_json() or {}
    user_message = data.get('message', '').strip()

    if not user_message or len(user_message) < 2:
        return {'response': 'Please type a valid question.'}, 400

    response = get_chatbot_response(user_message)
    return {'response': response}

# ─── ERROR HANDLERS ──────────────────────────────────────────────

@app.errorhandler(404)
def not_found(error):
    """Handle 404 - page not found"""
    return render_template('error.html', code=404, message='Page not found'), 404


@app.errorhandler(403)
def forbidden(error):
    """Handle 403 - access forbidden"""
    return render_template('error.html', code=403, message='Access denied'), 403


# ─── MAIN ───────────────────────────────────────────────────────

if __name__ == '__main__':
    # Initialize database and seed data
    init_db()
    seed_db()
    
    print("\n" + "="*50)
    print("🚀 Starting Complaint Management System")
    print("="*50)
    print("🌐 Open your browser: http://localhost:5000")
    print("="*50 + "\n")
    
    # Start Flask development server
    # debug=True: auto-reload on code changes, shows errors in browser
    app.run(debug=True, host='localhost', port=5000)
