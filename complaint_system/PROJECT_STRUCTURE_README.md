# Project Structure Guide

This file explains the purpose of every folder and file in this repository so the project can be handed off, reviewed, or extended with clear context.

## Repository Layout

### Top-level folders

- `templates/` - all Jinja templates, organized by role and purpose.
- `venv/` - local Python virtual environment used to run the app on this machine. It is generated locally and should not be edited by hand.

### Top-level data and config files

- `complaints.db` - the SQLite database file used by the app.
- `requirements.txt` - Python package dependencies for the project.
- `run.bat` - Windows batch file for starting the Flask app.
- `README.md` - original project README with the main overview and setup notes.
- `PROJECT_STRUCTURE_README.md` - this guide.

## Core Python Files

- `app.py` - the main Flask application. It defines routes, authentication flow, role-based access control, complaint workflow, assignment logic, admin actions, and app startup behavior.
- `models.py` - SQLAlchemy database models for users, complaints, and responses.
- `forms.py` - Flask-WTF forms used for login, registration, complaint submission, role updates, and other input handling.
- `ai_module.py` - complaint AI helpers such as classification, sentiment analysis, suggested response generation, and chatbot-style helpers.

## `templates/` Folder Layout

### Shared templates

- `templates/base.html` - the shared page layout and navigation shell used by most screens.
- `templates/error.html` - generic error page shown when something goes wrong.

### Auth templates

- `templates/auth/login.html` - login form and authentication page.
- `templates/auth/register.html` - new user registration page.

### User templates

- `templates/user/dashboard.html` - main landing page for regular users.
- `templates/user/submit.html` - complaint submission page for users.
- `templates/user/my_complaints.html` - list of complaints submitted by the logged-in user.
- `templates/user/complaint_detail.html` - complaint detail view for users, including status and responses.

### Manager templates

- `templates/manager/dashboard.html` - manager landing page with complaint workload and queue information.
- `templates/manager/complaint.html` - manager complaint detail page for review, response, and status updates.
- `templates/manager/team.html` - manager team overview page, likely showing manager workload, users, or assignment context.

### Admin templates

- `templates/admin/dashboard.html` - admin dashboard with system-wide stats and activity.
- `templates/admin/users.html` - main admin user management page with role controls and account actions.
- `templates/admin/user_detail.html` - detailed view for one user, including their complaints and admin actions.
- `templates/admin/database.html` - implemented as the Complaint Control Center (displayed in the navbar as "🛡️ Control Center"); shows system-wide stats, recent complaints, and allows admins to reply, resolve, or delete complaints directly from the interface.
- `templates/admin/assignments.html` - admin assignment manager page.

## Miscellaneous Files

- `user_dashboard_placeholder.txt` - placeholder text file that marks the user dashboard area or was used during development before the HTML dashboard was finalized.

## How The Files Fit Together

1. `app.py` is the central controller and decides which template to render.
2. `models.py` defines the database structure used by the routes.
3. `forms.py` validates incoming form data before it is saved or processed.
4. `ai_module.py` handles complaint analysis and response suggestions.
5. The HTML files render the interface for each role and workflow step.
6. `complaints.db` stores the live application data.

## Notes For Future Changes

- Keep shared navigation and layout behavior in `base.html` whenever possible. The navbar is centralized there.
- Navbar active state: links use the `.navbar-links a.active` class to highlight the current page for all roles, and the `.user-info` class prevents the profile icon from receiving the "glow" when navigating.
- Treat `venv/` as a generated local artifact.
- Keep role-specific screens inside the matching `templates/auth`, `templates/user`, `templates/admin`, and `templates/manager` folders.
- If you add new templates or routes, document them here so future edits stay consistent.
