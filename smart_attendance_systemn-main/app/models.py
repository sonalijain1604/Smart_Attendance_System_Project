from . import db
from flask_login import UserMixin

# ------------------ Class Table ------------------
class Class(db.Model):
    __tablename__ = 'class'
    class_id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(100), nullable=False)

    # Relationships
    students = db.relationship('Student', backref='class_', lazy=True)
    teachers = db.relationship('Teacher', backref='class_', lazy=True)
    subjects = db.relationship('Subject', backref='class_', lazy=True)


# ------------------ Teacher Table ------------------
class Teacher(UserMixin, db.Model):
    __tablename__ = 'teacher'
    teacher_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    contact = db.Column(db.String(15), nullable=True)
    class_in_charge = db.Column(db.Integer, db.ForeignKey('class.class_id'), nullable=True)
    profile_pic = db.Column(db.String(200), default='default.png')

    # For Flask-Login
    def get_id(self):
        return f"teacher-{self.teacher_id}"


# ------------------ Student Table ------------------
class Student(UserMixin, db.Model):
    __tablename__ = 'student'
    student_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    contact = db.Column(db.String(15), nullable=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class.class_id'), nullable=False)
    profile_pic = db.Column(db.String(200), default='default.png')
    face_encoding_path = db.Column(db.String(200), nullable=True)
    last_video_uploaded_at = db.Column(db.DateTime, nullable=True)

    # Relationship to facial data
    embedding = db.relationship('StudentEmbedding', uselist=False, back_populates='student')

    # For Flask-Login
    def get_id(self):
        return f"student-{self.student_id}"


# ------------------ Subject Table ------------------
class Subject(db.Model):
    __tablename__ = 'subject'
    subject_id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class.class_id'), nullable=False)
    subject_name = db.Column(db.String(100), nullable=False)

# ------------------ Attendance Logs Table ------------------
class AttendanceLog(db.Model):
    __tablename__ = 'attendance_log'
    attendance_id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class.class_id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.subject_id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.teacher_id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    periods = db.Column(db.String(50), nullable=True)  # to store "1,2,3"
    video_path = db.Column(db.String(255), nullable=True)

    # Explicit relationships (Fixes the issue)
    student = db.relationship('Student', backref='attendance_logs')
    subject = db.relationship('Subject', backref='attendance_logs')
    teacher = db.relationship('Teacher', backref='attendance_logs')
    class_ = db.relationship('Class', backref='attendance_logs')



# ------------------ Attendance Stats Table ------------------
class AttendanceSummary(db.Model):
    __tablename__ = 'attendance_stats'
    class_id = db.Column(db.Integer, db.ForeignKey('class.class_id'), primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.subject_id'), primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), primary_key=True)
    classes_present = db.Column(db.Integer, default=0)
    total_classes = db.Column(db.Integer, default=0)

    # Relationships (via backrefs in foreign models)


# ------------------ Students Facial Data Table ------------------
class StudentEmbedding(db.Model):
    __tablename__ = 'student_embeddings'
    student_id = db.Column(db.Integer, db.ForeignKey('student.student_id'), primary_key=True)
    embedding = db.Column(db.LargeBinary, nullable=False)

    student = db.relationship('Student', back_populates='embedding')