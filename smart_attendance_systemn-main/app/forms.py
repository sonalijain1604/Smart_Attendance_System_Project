from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    user_type = SelectField('Login as', choices=[
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student')
    ], validators=[DataRequired()])
    
    user_id = StringField('User ID', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')
