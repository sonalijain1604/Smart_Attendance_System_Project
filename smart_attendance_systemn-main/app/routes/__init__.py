from functools import wraps
from flask import redirect, url_for, flash, session
from flask_login import current_user

def role_required(role):
    from app.models import Teacher, Student
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Admin check (not using Flask-Login)
            if role == 'admin':
                if session.get('user_type') != 'admin':
                    flash("Admin access required!", "danger")
                    return redirect(url_for('auth.unauthorized'))
                return f(*args, **kwargs)

            # Other users (student/teacher) use Flask-Login
            if not current_user.is_authenticated:
                flash("Login required.", "warning")
                return redirect(url_for('auth.login'))

            if role == 'teacher' and not isinstance(current_user, Teacher):
                flash("Access denied: Teacher only!", "danger")
                return redirect(url_for('auth.unauthorized'))

            if role == 'student' and not isinstance(current_user, Student):
                flash("Access denied: Student only!", "danger")
                return redirect(url_for('auth.unauthorized'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator
