from flask import Flask, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from datetime import timedelta
import os


from dotenv import load_dotenv

load_dotenv()


db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI') or "sqlite:///../instance/app.db"
    app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER')
    
    # ⏳ Session timeout: 5 minutes of inactivity
    app.permanent_session_lifetime = timedelta(minutes=5)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.unauthorized_handler(lambda: redirect(url_for('auth.unauthorized')))

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import Teacher, Student
        if user_id.startswith("teacher-"):
            return Teacher.query.get(int(user_id.split("-")[1]))
        elif user_id.startswith("student-"):
            return Student.query.get(int(user_id.split("-")[1]))
        return None


    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.teacher import teacher_bp
    from app.routes.student import student_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)

    return app
