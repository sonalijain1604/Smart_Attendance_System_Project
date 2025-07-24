from flask import Blueprint, render_template, redirect, url_for, flash, session
from app.forms import LoginForm
from app.models import Teacher, Student
from flask import session
from flask_login import login_user, logout_user
import os
from dotenv import load_dotenv

load_dotenv()

auth_bp = Blueprint('auth', __name__)

# Hardcoded admin credentials
ADMIN_ID = os.environ.get('ADMIN_ID')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user_type = form.user_type.data
        user_id = form.user_id.data
        password = form.password.data

        if user_type == 'admin':
            if user_id == ADMIN_ID and password == ADMIN_PASSWORD:
                session.permanent = True
                session['user_type'] = 'admin'
                session['user_id'] = user_id
                session['is_authenticated'] = True
                return redirect(url_for('admin.dashboard'))
            else:
                flash('Invalid admin credentials.', 'danger')

        elif user_type == 'teacher':
            teacher = Teacher.query.filter_by(teacher_id=user_id).first()
            if teacher and teacher.password == password:
                session.permanent = True
                login_user(teacher)
                session['user_type'] = 'teacher'
                return redirect(url_for('teacher.dashboard'))
            else:
                flash('Invalid teacher credentials.', 'danger')

        elif user_type == 'student':
            student = Student.query.filter_by(student_id=user_id).first()
            if student and student.password == password:
                session.permanent = True
                login_user(student)
                session['user_type'] = 'student'
                return redirect(url_for('student.dashboard'))
            else:
                flash('Invalid student credentials.', 'danger')

    return render_template('auth/login.html', form=form)


from flask_login import logout_user

@auth_bp.route('/logout')
def logout():
    logout_user()
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for('auth.login'))

@auth_bp.route('/unauthorized')
def unauthorized():
    return render_template('auth/unauthorized.html'), 403
