# Smart Complaint Management System

Smart Complaint Management System is a Flask-based web application for collecting, classifying, assigning, and tracking complaints in a simple college-style workflow. It supports three user roles, AI-assisted complaint triage, manager response handling, and an admin control panel for user and assignment management.

This README is written as project context for ChatGPT, GitHub Copilot, or any other coding assistant. It explains how the app is organized, what each part does, and what assumptions are safe to make when generating new code or prompts.

## Project Goal

The application helps a user submit a complaint, automatically analyzes the complaint text, routes it to a manager, and lets admins supervise users and complaint assignments. It is intentionally lightweight and educational, not an enterprise-grade workflow engine.

## Tech Stack

- Python 3
- Flask 3
- Flask-SQLAlchemy with SQLite
- Flask-Login for authentication and session handling
- Flask-WTF for form validation and CSRF protection
- Werkzeug for password hashing
- scikit-learn for complaint classification
- NLTK VADER for sentiment analysis
- Jinja2 templates with HTML, CSS, and vanilla JavaScript

## How The App Is Structured

The app is built as a single Flask project inside the `complaint_system` folder. The main application file uses a dedicated `templates/` directory, with role-based subfolders for auth, user, admin, and manager screens.

Important files:

- `app.py` - main Flask app, route definitions, database initialization, role logic, and API endpoints
- `models.py` - SQLAlchemy models for users, complaints, and responses
- `forms.py` - Flask-WTF forms for login, registration, complaint submission, and manager updates
- `ai_module.py` - AI helper functions for complaint classification, sentiment analysis, response generation, and chatbot replies
- `templates/base.html` - shared layout and navigation
- `templates/auth/login.html` - login page
- `templates/auth/register.html` - registration page
- `templates/user/dashboard.html` - end-user dashboard
- `templates/user/submit.html` - complaint submission page
- `templates/user/my_complaints.html` - user complaint list page
- `templates/user/complaint_detail.html` - complaint detail page
- `templates/manager/dashboard.html` - manager landing page
- `templates/manager/complaint.html` - manager complaint detail page
- `templates/admin/dashboard.html` - admin landing page
- `templates/admin/users.html` - admin user management page
- `templates/admin/database.html` - admin control center with direct complaint reply, resolve, and delete actions
- `templates/admin/assignments.html` - admin assignment manager page
- `templates/error.html` - error display page

## User Roles

The system has three roles:

- `user` - submits complaints, tracks their status, and rates resolved complaints
- `manager` - reviews assigned complaints, responds to users, updates status, and manages internal notes
- `admin` - oversees users, managers, and complaint assignments

Role-based access control is enforced in the Flask routes with `@login_required` plus role checks inside each view.

## Main Workflow

1. A user registers or logs in.
2. The user submits a complaint through the complaint form.
3. The app classifies the complaint category with TF-IDF + Naive Bayes.
4. The app analyzes sentiment with VADER and derives priority.
5. The app generates a suggested AI response.
6. The complaint is assigned to a manager.
7. The manager reviews the complaint, posts responses, and updates the status.
8. The admin monitors users, manager load, and complaint assignment activity.

## AI And Automation

The AI logic is intentionally simple and rule-driven so it is easy to understand and modify.

### Complaint Classification

`ai_module.py` uses a small hand-written training set and a text pipeline:

- `TfidfVectorizer`
- `MultinomialNB`

It predicts one of these categories:

- `Technical`
- `Billing`
- `Service`
- `General`

### Sentiment And Priority

The app uses VADER sentiment analysis to infer whether a complaint is positive, neutral, or negative. Priority is then derived from sentiment plus urgency keywords.

### AI Response Generation

Instead of calling an external LLM, the project generates templated suggested responses based on category and sentiment. This keeps the project fast, offline-friendly, and easy to demo.

### Chatbot Endpoint

The app also exposes a small FAQ-style chatbot endpoint for simple intent matching. It answers common questions like complaint tracking, login help, and how to submit a complaint.

## Key Routes

The Flask app exposes the following important routes:

- `/` - redirects users based on role
- `/register` - create a new user account
- `/login` - log in
- `/logout` - log out
- `/user/dashboard` - user home page
- `/user/submit` - submit a complaint
- `/user/complaints` - view submitted complaints
- `/user/complaint/<id>` - complaint detail page
- `/user/complaint/<id>/rate` - rate a resolved complaint
- `/manager/dashboard` - manager home page
- `/manager/team` - manager team overview page
- `/manager/complaint/<id>` - review and update a specific complaint
- `/admin/dashboard` - admin home page
- `/admin/users` - user administration page
- `/admin/assignments` - admin assignment manager page
- `/admin/users/create-manager` - create a manager account
- `/admin/users/<id>/role` - change a user role
- `/admin/users/<id>/deactivate` - deactivate a user
- `/api/chat` and `/api/chatbot` - chatbot API endpoints

## Database Models

The database is defined in `models.py` and uses SQLite tables:

- `User`
  - `username`
  - `email`
  - `password_hash`
  - `role`
  - `is_active_user`
  - `created_at`

- `Complaint`
  - `user_id`
  - `title`
  - `description`
  - `category`
  - `priority`
  - `sentiment`
  - `status`
  - `ai_response`
  - `internal_notes`
  - `assigned_to`
  - `created_at`
  - `resolved_at`
  - `rating`

- `Response`
  - `complaint_id`
  - `author_id`
  - `message`
  - `created_at`

Relationships connect users to their complaints, manager assignments, and response history.

## Default Test Accounts

The app seeds a few demo accounts when the database is empty:

- Admin: `admin@college.com` / `admin123`
- Manager 1: `manager1@college.com` / `manager123`
- Manager 2: `manager2@college.com` / `manager123`
- User: `user@college.com` / `user123`

## Project Summary In One Sentence

This project is a simple Flask complaint management system with AI-assisted complaint classification, role-based dashboards, manager response workflows, and admin oversight.
