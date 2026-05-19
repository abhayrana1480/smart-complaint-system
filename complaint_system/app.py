"""
Smart Complaint Management System - Main Flask Application
A simple, college-friendly complaint management system with AI classification and sentiment analysis
"""

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Complaint, Response
from forms import LoginForm, RegisterForm, ComplaintForm, ResponseForm
from ai_module import process_complaint_with_ai, get_chatbot_response
from datetime import datetime, timedelta
import os
from sqlalchemy import case, inspect, text

# Initialize Flask app with a dedicated templates folder
app = Flask(__name__, template_folder='templates')

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

    # Handle the rename from is_active_user to is_active
    if 'is_active_user' in user_columns and 'is_active' not in user_columns:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE users RENAME COLUMN is_active_user TO is_active'))
        print("✅ Renamed column: users.is_active_user → users.is_active")
    elif 'is_active' not in user_columns:
        # For fresh databases, just add the is_active column
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1'))
            connection.execute(text('UPDATE users SET is_active = 1 WHERE is_active IS NULL'))
        print("✅ Added missing column: users.is_active")

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
    Only assigns to active managers (is_active == True).
    """
    managers = User.query.filter_by(role='manager', is_active=True).all()
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
    """Public landing page for guests, dashboard redirect for signed-in users."""
    if current_user.is_authenticated:
        # Redirect based on role
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'manager':
            return redirect(url_for('manager_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return render_template('home.html')


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
    return render_template('auth/register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page with form validation and CSRF protection
    Uses Flask-WTF to validate email/password before authenticating.
    Also checks if the user account is deactivated (is_active == False).
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
            # Check if user account is deactivated (is_active == False)
            if not user.is_active:
                flash('❌ Your account has been temporarily deactivated. Please contact the administrator.', 'error')
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
    
    return render_template('auth/login.html', form=form)


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
        'user/dashboard.html',
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

    return render_template('user/submit.html', form=form)


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

    return render_template('user/my_complaints.html', complaints=complaints)


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
    
    return render_template('user/complaint_detail.html', complaint=complaint)


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
        'manager/dashboard.html',
        complaints=assigned_complaints,
        now=datetime.utcnow()
    )

# ─── MANAGER TEAM OVERVIEW ROUTE ────────────────────────────────

@app.route('/manager/team')
@login_required
def manager_team():
    """
    Manager team overview page.
    Shows all complaints, workload stats, and a read-only team board.
    """
    if current_user.role != 'manager':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    # Use aliases because Complaint has two links to User.
    from sqlalchemy.orm import aliased
    ManagerUser = aliased(User)
    SubmitterUser = aliased(User)

    # Load every complaint with both the assigned manager and the submitter.
    all_rows = (
        db.session.query(Complaint, ManagerUser, SubmitterUser)
        .outerjoin(ManagerUser, Complaint.assigned_to == ManagerUser.id)
        .join(SubmitterUser, Complaint.user_id == SubmitterUser.id)
        .order_by(Complaint.created_at.desc())
        .all()
    )

    # Show every manager in the team cards and workload summary.
    all_managers = (
        User.query.filter_by(role='manager')
        .order_by(User.username.asc())
        .all()
    )

    # Count recent resolution activity for each manager.
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    workload_stats = []

    for manager in all_managers:
        total_assigned = Complaint.query.filter(
            Complaint.assigned_to == manager.id
        ).count()

        open_count = Complaint.query.filter(
            Complaint.assigned_to == manager.id,
            Complaint.status.in_(['open', 'in_progress'])
        ).count()

        resolved_this_week = Complaint.query.filter(
            Complaint.assigned_to == manager.id,
            Complaint.status == 'resolved',
            Complaint.resolved_at.isnot(None),
            Complaint.resolved_at >= one_week_ago
        ).count()

        workload_stats.append({
            'manager': manager,
            'total_assigned': total_assigned,
            'open_count': open_count,
            'resolved_this_week': resolved_this_week,
        })

    return render_template(
        'manager/team.html',
        all_rows=all_rows,
        all_managers=all_managers,
        workload_stats=workload_stats,
        current_user_id=current_user.id
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

    return render_template('manager/complaint.html', complaint=complaint, form=form)


# ─── ADMIN ASSIGNMENT MANAGER ROUTE ─────────────────────────────

@app.route('/admin/assignments', methods=['GET', 'POST'])
@login_required
def admin_assignments():
    """
    Admin assignment manager page.
    Handles complaint filtering, workload summaries, and reassignment.
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    # Use aliases because Complaint has both assigned_to and user_id foreign keys.
    from sqlalchemy.orm import aliased
    ManagerUser = aliased(User)
    SubmitterUser = aliased(User)

    # Handle AJAX and normal form submissions for reassignment.
    if request.method == 'POST':
        complaint_id = request.form.get('complaint_id', '').strip()
        new_manager_id = request.form.get('new_manager_id', '').strip()
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        # Validate the complaint id before looking it up.
        try:
            complaint_id_int = int(complaint_id)
        except (TypeError, ValueError):
            if is_ajax:
                return jsonify({'success': False, 'error': 'Invalid complaint id.'}), 400
            flash('❌ Invalid complaint id.', 'error')
            return redirect(url_for('admin_assignments'))

        complaint = Complaint.query.get(complaint_id_int)
        if not complaint:
            if is_ajax:
                return jsonify({'success': False, 'error': 'Complaint not found.'}), 404
            flash('❌ Complaint not found.', 'error')
            return redirect(url_for('admin_assignments'))

        # Empty manager id means unassign the complaint.
        if new_manager_id == '':
            complaint.assigned_to = None
            manager_name = 'Unassigned'
        else:
            # Validate the selected manager before saving.
            try:
                manager_id_int = int(new_manager_id)
            except (TypeError, ValueError):
                if is_ajax:
                    return jsonify({'success': False, 'error': 'Invalid manager selection.'}), 400
                flash('❌ Invalid manager selection.', 'error')
                return redirect(url_for('admin_assignments'))

            manager = User.query.get(manager_id_int)
            if not manager or manager.role != 'manager':
                if is_ajax:
                    return jsonify({'success': False, 'error': 'Selected user is not a manager.'}), 400
                flash('❌ Selected user is not a manager.', 'error')
                return redirect(url_for('admin_assignments'))

            complaint.assigned_to = manager.id
            manager_name = manager.username

        db.session.commit()

        if is_ajax:
            return jsonify({'success': True, 'manager_name': manager_name})

        flash('Complaint reassigned successfully', 'success')
        return redirect(url_for('admin_assignments'))

    # Read filters from the URL so the page can keep the current selection.
    filter_manager = request.args.get('manager', 'all').strip()
    filter_status = request.args.get('status', 'all').strip().lower()

    rows_query = (
        db.session.query(Complaint, ManagerUser, SubmitterUser)
        .outerjoin(ManagerUser, Complaint.assigned_to == ManagerUser.id)
        .join(SubmitterUser, Complaint.user_id == SubmitterUser.id)
    )

    # Apply the manager filter from the dropdown.
    if filter_manager == 'unassigned':
        rows_query = rows_query.filter(Complaint.assigned_to.is_(None))
    elif filter_manager not in ('', 'all'):
        try:
            manager_id_int = int(filter_manager)
            rows_query = rows_query.filter(Complaint.assigned_to == manager_id_int)
        except ValueError:
            pass

    # Apply the status filter from the dropdown.
    valid_statuses = {'open', 'in_progress', 'resolved', 'closed'}
    if filter_status in valid_statuses:
        rows_query = rows_query.filter(Complaint.status == filter_status)

    rows = rows_query.order_by(Complaint.created_at.desc()).all()

    # Load all managers for the dropdown and the workload summary.
    all_managers = (
        User.query.filter_by(role='manager')
        .order_by(User.username.asc())
        .all()
    )

    workload_summary = []
    total_complaints = Complaint.query.count()
    unassigned_count = Complaint.query.filter(Complaint.assigned_to.is_(None)).count()
    active_managers_count = User.query.filter_by(role='manager', is_active=True).count()
    resolved_complaints = Complaint.query.filter_by(status='resolved').count()

    for manager in all_managers:
        status_rows = (
            db.session.query(Complaint.status, db.func.count(Complaint.id))
            .filter(Complaint.assigned_to == manager.id)
            .group_by(Complaint.status)
            .all()
        )

        status_counts = {status: count for status, count in status_rows}

        workload_summary.append({
            'manager': manager,
            'total_assigned': sum(status_counts.values()),
            'open_count': status_counts.get('open', 0),
            'in_progress_count': status_counts.get('in_progress', 0),
            'resolved_count': status_counts.get('resolved', 0),
        })

    return render_template(
        'admin/assignments.html',
        rows=rows,
        all_managers=all_managers,
        workload_summary=workload_summary,
        filter_manager=filter_manager,
        filter_status=filter_status,
        total_complaints=total_complaints,
        unassigned_count=unassigned_count,
        active_managers_count=active_managers_count,
        resolved_complaints=resolved_complaints,
    )# ─── ADMIN ROUTES (placeholder for now) ─────────────────────────

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
            'text': f"{response.response_author.username} replied on Complaint #{response.complaint_id}"
        })

    recent_activity = sorted(recent_activity, key=lambda item: item['time'], reverse=True)[:10]

    return render_template(
        'admin/dashboard.html',
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

# ─── ENHANCED ADMIN ROUTES ──────────────────────────────────────

## B1. ENHANCED USER LIST - Replace existing /admin/users route
@app.route('/admin/users')
@login_required
def admin_users():
    """
    Admin user management page: view all users (active and inactive).
    Shows user stats, activity, and action buttons for deactivate/reactivate/delete.
    Separates active and inactive users into two tables.
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    # Query active and inactive users
    active_users = User.query.filter_by(is_active=True).order_by(User.created_at.desc()).all()
    inactive_users = User.query.filter_by(is_active=False).order_by(User.created_at.desc()).all()

    # Build dictionaries for complaint counts and last activity dates
    complaint_counts = {}
    last_active = {}

    for user in active_users + inactive_users:
        # Count complaints submitted by this user
        complaint_counts[user.id] = Complaint.query.filter_by(user_id=user.id).count()
        
        # Get their last activity (most recent complaint)
        last_complaint = Complaint.query.filter_by(user_id=user.id).order_by(Complaint.created_at.desc()).first()
        if last_complaint:
            last_active[user.id] = last_complaint.created_at.strftime('%Y-%m-%d %H:%M')
        else:
            last_active[user.id] = 'No activity'

    return render_template(
        'admin/users.html',
        active_users=active_users,
        inactive_users=inactive_users,
        complaint_counts=complaint_counts,
        last_active=last_active
    )


## B2. DEACTIVATE USER - Temporarily disable login
@app.route('/admin/deactivate/<int:user_id>', methods=['POST'])
@login_required
def deactivate_user(user_id):
    """
    Deactivate a user account (temporarily disable login, keep data).
    Safety checks: Cannot deactivate admin accounts or self.
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    # Find user - if not found, flash error and redirect
    user = User.query.get(user_id)
    if not user:
        flash('❌ User not found.', 'error')
        return redirect(url_for('admin_users'))

    # Safety check: cannot deactivate admin accounts
    if user.role == 'admin':
        flash('❌ Cannot deactivate an admin account.', 'error')
        return redirect(url_for('admin_users'))

    # Check if already deactivated
    if not user.is_active:
        flash(f'❌ User {user.username} is already deactivated.', 'error')
        return redirect(url_for('admin_users'))

    # Deactivate the user
    user.is_active = False
    db.session.commit()
    
    flash(f'✅ User {user.username} has been temporarily deactivated.', 'success')
    return redirect(url_for('admin_users'))


## B3. REACTIVATE USER - Re-enable login
@app.route('/admin/reactivate/<int:user_id>', methods=['POST'])
@login_required
def reactivate_user(user_id):
    """
    Reactivate a deactivated user account (re-enable login).
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    # Find user - if not found, flash error and redirect
    user = User.query.get(user_id)
    if not user:
        flash('❌ User not found.', 'error')
        return redirect(url_for('admin_users'))

    # Check if already active
    if user.is_active:
        flash(f'❌ User {user.username} is already active.', 'error')
        return redirect(url_for('admin_users'))

    # Reactivate the user
    user.is_active = True
    db.session.commit()
    
    flash(f'✅ User {user.username} has been reactivated successfully.', 'success')
    return redirect(url_for('admin_users'))


## B4. PERMANENT DELETE USER - Delete user and all their data
@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """
    Permanently delete a user and all their submitted complaints and responses.
    Safety checks: Cannot delete admin accounts, cannot delete self.
    Unassigns any complaints that were assigned to this user (as a manager).
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    # Find user - if not found, flash error and redirect
    user = User.query.get(user_id)
    if not user:
        flash('❌ User not found.', 'error')
        return redirect(url_for('admin_users'))

    # Safety check: cannot delete admin accounts
    if user.role == 'admin':
        flash('❌ Cannot delete an admin account.', 'error')
        return redirect(url_for('admin_users'))

    # Safety check: cannot delete self
    if user.id == current_user.id:
        flash('❌ You cannot delete your own account.', 'error')
        return redirect(url_for('admin_users'))

    # Before deleting the user, unassign any complaints they were managing
    complaints_assigned = Complaint.query.filter_by(assigned_to=user.id).all()
    for complaint in complaints_assigned:
        complaint.assigned_to = None
    db.session.commit()

    # Now delete the user (cascade will delete their submitted complaints and responses)
    username = user.username
    db.session.delete(user)
    db.session.commit()

    flash(f'✅ User {username} and all their data have been permanently deleted.', 'success')
    return redirect(url_for('admin_users'))


## B5. VIEW USER DETAIL - Show full user profile and complaints
@app.route('/admin/user/<int:user_id>')
@login_required
def admin_user_detail(user_id):
    """
    Admin view of a single user's profile and complaint history.
    Shows user stats, all their submitted complaints, and all their responses.
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    # Find user - if not found, return 404
    user = User.query.get_or_404(user_id)

    # Get all complaints submitted by this user
    complaints = Complaint.query.filter_by(user_id=user.id).order_by(Complaint.created_at.desc()).all()

    # Get all responses written by this user
    responses = Response.query.filter_by(author_id=user.id).order_by(Response.created_at.desc()).all()

    # Calculate stats
    total_complaints = len(complaints)
    open_count = sum(1 for c in complaints if c.status == 'open')
    resolved_count = sum(1 for c in complaints if c.status == 'resolved')
    
    # Calculate average rating (only for complaints with ratings)
    ratings = [c.rating for c in complaints if c.rating is not None]
    avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

    return render_template(
        'admin/user_detail.html',
        user=user,
        complaints=complaints,
        responses=responses,
        total_complaints=total_complaints,
        open_count=open_count,
        resolved_count=resolved_count,
        avg_rating=avg_rating
    )


## B6. ADMIN DATABASE OVERVIEW - System-wide stats
@app.route('/admin/database')
@login_required
def admin_database():
    """
    Admin control center showing system-wide statistics and direct complaint actions.
    Displays counts of users, complaints, responses, and recent activity.
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    # User stats
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    inactive_users = User.query.filter_by(is_active=False).count()

    # Complaint stats
    total_complaints = Complaint.query.count()
    open_complaints = Complaint.query.filter_by(status='open').count()
    in_progress_complaints = Complaint.query.filter_by(status='in_progress').count()
    resolved_complaints = Complaint.query.filter_by(status='resolved').count()
    closed_complaints = Complaint.query.filter_by(status='closed').count()
    unassigned_complaints = Complaint.query.filter(Complaint.assigned_to == None).count()
    high_priority_complaints = Complaint.query.filter_by(priority='high').count()

    # Response stats
    total_responses = Response.query.count()

    # Get 10 most recent complaints
    recent_complaints = Complaint.query.order_by(Complaint.created_at.desc()).limit(10).all()

    return render_template(
        'admin/database.html',
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        total_complaints=total_complaints,
        open_complaints=open_complaints,
        in_progress_complaints=in_progress_complaints,
        resolved_complaints=resolved_complaints,
        closed_complaints=closed_complaints,
        unassigned_complaints=unassigned_complaints,
        high_priority_complaints=high_priority_complaints,
        total_responses=total_responses,
        recent_complaints=recent_complaints
    )


@app.route('/admin/database/complaint/<int:complaint_id>/action', methods=['POST'])
@login_required
def admin_database_complaint_action(complaint_id):
    """
    Allow admins to reply to, resolve, or delete a complaint directly from the database dashboard.
    """
    if current_user.role != 'admin':
        flash('❌ Unauthorized!', 'error')
        return redirect(url_for('index'))

    complaint = Complaint.query.get_or_404(complaint_id)
    action = request.form.get('action', '').strip().lower()
    message = request.form.get('message', '').strip()

    if action == 'delete':
        complaint_title = complaint.title
        db.session.delete(complaint)
        db.session.commit()
        flash(f'✅ Complaint "{complaint_title}" has been permanently deleted.', 'success')
        return redirect(url_for('admin_database'))

    if action not in {'reply', 'resolve'}:
        flash('❌ Invalid complaint action.', 'error')
        return redirect(url_for('admin_database'))

    if action == 'reply' and not message:
        flash('❌ Please enter a reply before sending.', 'error')
        return redirect(url_for('admin_database'))

    if action == 'resolve' and not message:
        message = f'Complaint #{complaint.id} resolved directly from the admin control center.'

    if complaint.assigned_to is None and action == 'reply':
        complaint.status = 'in_progress'
    elif action == 'reply' and complaint.status == 'open':
        complaint.status = 'in_progress'

    if action == 'resolve':
        complaint.status = 'resolved'
        if complaint.resolved_at is None:
            complaint.resolved_at = datetime.utcnow()
    elif complaint.status == 'resolved' and action == 'reply':
        complaint.status = 'in_progress'
        complaint.resolved_at = None

    response = Response(
        complaint_id=complaint.id,
        author_id=current_user.id,
        message=message,
    )

    db.session.add(response)
    db.session.commit()

    if action == 'resolve':
        flash(f'✅ Complaint #{complaint.id} has been resolved.', 'success')
    else:
        flash(f'✅ Reply saved for complaint #{complaint.id}.', 'success')

    return redirect(url_for('admin_database'))


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

    # Prevent admins changing their own role from the UI to avoid accidental lockout
    if current_user.id == user.id:
        flash('❌ You cannot change your own role.', 'error')
        return redirect(url_for('admin_users'))

    # Prevent removing the last remaining admin
    if user.role == 'admin' and new_role != 'admin':
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            flash('❌ Cannot remove the last admin account.', 'error')
            return redirect(url_for('admin_users'))

    user.role = new_role
    db.session.commit()
    flash(f'✅ Role updated for {user.username} to {new_role}.', 'success')
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
