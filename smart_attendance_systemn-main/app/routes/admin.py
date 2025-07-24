from flask import Blueprint, render_template, redirect, url_for, request, flash
from app.models import db, Teacher, Student, Class, Subject, AttendanceLog, AttendanceSummary
import csv
from app.routes import role_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------- Dashboard ----------
@admin_bp.route('/dashboard')
@role_required('admin')
def dashboard():
    teachers = Teacher.query.all()
    students = Student.query.all()
    classes = Class.query.all()
    subjects = Subject.query.all()
    return render_template('admin/dashboard.html', teachers=teachers, students=students, classes=classes, subjects=subjects)

# ---------- Manual Upload via Form (/upload_csv) ----------
@admin_bp.route('/upload_csv', methods=['GET', 'POST'])
@role_required('admin')
def manual_csv_upload():
    if request.method == 'POST':
        csv_type = request.form.get('csv_type')
        file = request.files.get('csv_file')

        if not file or not allowed_file(file.filename):
            flash('Please upload a valid CSV file.', 'danger')
            return redirect(request.url)

        stream = file.stream.read().decode("UTF8").splitlines()
        csv_input = csv.reader(stream)
        header = next(csv_input)  # Skip header row

        inserted = 0

        try:
            if csv_type == 'students':
                for row in csv_input:
                    student_id, name, password, class_id, contact = row
                    student = Student(
                        student_id=int(student_id),
                        name=name.strip(),
                        password=password.strip(),
                        # password=generate_password_hash(password.strip()),
                        class_id=int(class_id),
                        contact=contact.strip(),
                        profile_pic='default.jpg'
                    )
                    db.session.merge(student)
                    inserted += 1

                    #  Retrieve all subjects for the class
                    subjects = Subject.query.filter_by(class_id=class_id).all()

                    # Add an attendance summary entry for each subject of the class
                    for subject in subjects:
                        summary = AttendanceSummary(
                            class_id=int(class_id),
                            student_id=int(student_id),
                            subject_id=subject.subject_id,  # Associate with the correct subject
                            classes_present=0,
                            total_classes=0
                        )
                        db.session.add(summary)

                    # Commit all the attendance summaries to the database
                    db.session.commit()

            elif csv_type == 'teachers':
                for row in csv_input:
                    teacher_id, name, password, class_in_charge, contact = row
                    class_in_charge = None if class_in_charge.lower() == 'none' else int(class_in_charge)
                    teacher = Teacher(
                        teacher_id=int(teacher_id),
                        name=name.strip(),
                        password=password.strip(),
                        # password=generate_password_hash(password.strip()),
                        class_in_charge=class_in_charge,
                        contact=contact.strip(),
                        profile_pic='default.jpg'
                    )
                    db.session.merge(teacher)
                    inserted += 1

            elif csv_type == 'classes':
                for row in csv_input:
                    class_id, class_name = row
                    cls = Class(
                        class_id=int(class_id),
                        class_name=class_name.strip()
                    )
                    db.session.merge(cls)
                    inserted += 1

            elif csv_type == 'subjects':
                for row in csv_input:
                    class_id, subject_id, subject_name = row
                    subj = Subject(
                        subject_id=int(subject_id),
                        subject_name=subject_name.strip(),
                        class_id=int(class_id)
                    )
                    db.session.merge(subj)
                    inserted += 1

            db.session.commit()
            flash(f"{inserted} record(s) inserted into {csv_type}.", "success")

        except Exception as e:
            flash(f"Error processing CSV: {str(e)}", "danger")

        return redirect(url_for('admin.manual_csv_upload'))

    return render_template("admin/upload_csv.html")


# View Teachers
@admin_bp.route('/teachers')
@role_required('admin')
def view_teachers():
    teachers = Teacher.query.all()
    return render_template('admin/view_teachers.html', teachers=teachers)

# View Students
@admin_bp.route('/students')
@role_required('admin')
def view_students():
    students = Student.query.all()
    return render_template('admin/view_students.html', students=students)

# View Classes
@admin_bp.route('/classes')
@role_required('admin')
def view_classes():
    classes = Class.query.all()
    return render_template('admin/view_classes.html', classes=classes)

# View Subjects
@admin_bp.route('/subjects')
@role_required('admin')
def view_subjects():
    subjects = Subject.query.all()
    return render_template('admin/view_subjects.html', subjects=subjects)

# Add Student
@admin_bp.route('/students/add', methods=['GET', 'POST'])
@role_required('admin')
def add_student():
    if request.method == 'POST':
        student_id = request.form['student_id']
        name = request.form['name']
        password = request.form['password']
        class_id = request.form['class_id']
        contact = request.form['contact']

        student = Student(
            student_id=int(student_id),
            name=name,
            password=password,
            # password=generate_password_hash(password),
            class_id=int(class_id),
            contact=contact,
            profile_pic='default.jpg'
        )
        db.session.add(student)
        db.session.commit()

        #  Retrieve all subjects for the class
        subjects = Subject.query.filter_by(class_id=class_id).all()

        # Add an attendance summary entry for each subject of the class
        for subject in subjects:
            summary = AttendanceSummary(
                class_id=int(class_id),
                student_id=int(student_id),
                subject_id=subject.subject_id,  # Associate with the correct subject
                classes_present=0,
                total_classes=0
            )
            db.session.add(summary)

        # Commit all the attendance summaries to the database
        db.session.commit()

        flash("Student added successfully!", "success")
        return redirect(url_for('admin.view_students'))

    classes = Class.query.all()
    return render_template('admin/add_student.html', classes=classes)

# Add Teacher
@admin_bp.route('/teachers/add', methods=['GET', 'POST'])
@role_required('admin')
def add_teacher():
    if request.method == 'POST':
        teacher_id = request.form['teacher_id']
        name = request.form['name']
        password = request.form['password']
        class_in_charge = request.form['class_in_charge']
        contact = request.form['contact']

        teacher = Teacher(
            teacher_id=int(teacher_id),
            name=name,
            password=password,
            # password=generate_password_hash(password),
            class_in_charge=None if class_in_charge.lower() == 'none' else int(class_in_charge),
            contact=contact,
            profile_pic='default.jpg'
        )
        db.session.add(teacher)
        db.session.commit()
        flash("Teacher added successfully!", "success")
        return redirect(url_for('admin.view_teachers'))

    # 🛠️ Exclude classes that are already assigned
    assigned_class_ids = db.session.query(Teacher.class_in_charge).filter(
        Teacher.class_in_charge.isnot(None)
    ).subquery()

    classes = Class.query.filter(~Class.class_id.in_(assigned_class_ids)).all()

    return render_template('admin/add_teacher.html', classes=classes)


# Delete Teacher
@admin_bp.route('/teachers/delete/<int:teacher_id>', methods=['POST'])
@role_required('admin')
def delete_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    db.session.delete(teacher)
    db.session.commit()
    flash("Teacher deleted successfully!", "success")
    return redirect(url_for('admin.view_teachers'))


# Delete Student
@admin_bp.route('/students/delete/<int:student_id>', methods=['POST'])
@role_required('admin')
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)

    # Delete all attendance logs for this student
    AttendanceLog.query.filter_by(student_id=student_id).delete()

    # Optionally, also delete from AttendanceSummary table
    AttendanceSummary.query.filter_by(student_id=student_id).delete()

    # Delete the student
    db.session.delete(student)
    db.session.commit()

    flash("Student and associated attendance records deleted successfully!", "success")
    return redirect(url_for('admin.view_students'))


# Edit Teacher
@admin_bp.route('/teachers/edit/<int:teacher_id>', methods=['GET', 'POST'])
@role_required('admin')
def edit_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)

    # Fix: Filter classes not already assigned to other teachers
    assigned_class_ids = db.session.query(Teacher.class_in_charge).filter(
        Teacher.class_in_charge.isnot(None),
        Teacher.teacher_id != teacher_id
    ).subquery()

    available_classes = Class.query.filter(~Class.class_id.in_(assigned_class_ids)).all()

    if request.method == 'POST':
        teacher.name = request.form['name']
        teacher.contact = request.form['contact']
        teacher.class_in_charge = request.form.get('class_in_charge') or None
        db.session.commit()
        flash("Teacher updated successfully!", "success")
        return redirect(url_for('admin.view_teachers'))

    return render_template('admin/edit_teacher.html', teacher=teacher, available_classes=available_classes)

# Edit Student
@admin_bp.route('/student/edit/<int:student_id>', methods=['GET', 'POST'])
@role_required('admin')
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)

    if request.method == 'POST':
        # Only update contact information
        student.contact = request.form['contact']
        db.session.commit()

        flash("Student contact updated successfully.", "success")
        return redirect(url_for('admin.view_students'))

    # Get the class name from the class ID
    student.class_name = Class.query.get(student.class_id).class_name

    return render_template('admin/edit_student.html', student=student)