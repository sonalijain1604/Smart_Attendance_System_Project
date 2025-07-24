from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context
from flask_login import login_required, current_user
from datetime import datetime
import os
from app import db
from app.models import Teacher, Class, Subject, AttendanceLog, AttendanceSummary, Student  # <-- Import Student
from app.routes import role_required
import queue
import json

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

UPLOAD_FOLDER = 'app/static/uploads/class_videos'
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov'}

def allowed_video_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


@teacher_bp.route('/dashboard')
@login_required
@role_required('teacher')
def dashboard():
    if not isinstance(current_user, Teacher):
        flash("Access denied!", "danger")
        return redirect(url_for('auth.login'))

    class_name = None
    if current_user.class_in_charge:
        class_obj = Class.query.get(current_user.class_in_charge)
        class_name = class_obj.class_name if class_obj else "N/A"

    # Fetch classes
    teacher_classes = Class.query.all()

    # Fetch subjects linked to those classes
    teacher_subjects = Subject.query.filter(Subject.class_id.in_([cls.class_id for cls in teacher_classes])).all()

    return render_template(
        'teacher/dashboard.html',
        teacher=current_user,
        class_name=class_name,
        teacher_classes=teacher_classes,
        teacher_subjects=teacher_subjects
    )

client_queues = {}

@teacher_bp.route('/upload_video_progress')
@login_required
@role_required('teacher')
def upload_video_progress():
    teacher_id = current_user.teacher_id
    q = queue.Queue()
    client_queues[teacher_id] = q 

    def event_stream():
        while True:
            try:
                data = q.get(timeout=60)
                yield f"data: {data}\n\n"
                if '"percent": 100' in data:
                    break
            except queue.Empty:
                break

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

def send_progress(teacher_id, step, percent):
    if teacher_id in client_queues:
        update = {'step': step, 'percent': percent}
        client_queues[teacher_id].put(json.dumps(update))
        if percent == 100:
            del client_queues[teacher_id]



@teacher_bp.route('/upload_video', methods=['POST'])
@login_required
@role_required('teacher')
def upload_video():
    if 'video' not in request.files:
        flash("No file part", "danger")
        return redirect(url_for('teacher.dashboard'))

    video = request.files['video']
    
    class_id = request.form.get('class_id')
    subject_id = request.form.get('subject_id')
    periods = request.form.get('periods', '')
    date = request.form.get('date')

    if video.filename == '':
        flash("No selected file", "danger")
        return redirect(url_for('teacher.dashboard'))
    
    
    filename = f"{class_id}_{subject_id}_{current_user.teacher_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if allowed_video_file(filepath):

        video.save(filepath)
        send_progress(current_user.teacher_id, "📥 Video uploaded successfully", 5)

        try:
            import app.ml.recognise as recog
            
            send_progress(current_user.teacher_id, "🎞️ Extracting faces from video...", 25)
            detected_faces = recog.extract_faces(filepath)
            print(f"[INFO] Extracted {len(detected_faces)} faces.")

            send_progress(current_user.teacher_id, "🧠 Generating face embeddings...", 45)
            embeddings = [recog.generate_face_embedding(face) for face in detected_faces]
            valid_embeddings = [emb for emb in embeddings if emb is not None]
            print(f"[INFO] Generated {len(valid_embeddings)} valid embeddings.")

            if not valid_embeddings:
                send_progress(current_user.teacher_id, "❌ No valid embeddings found", 100)
                flash("No faces detected or valid embeddings found.", "danger")
                return redirect(url_for('teacher.dashboard'))

            send_progress(current_user.teacher_id, "📚 Loading registered student data...", 65)
            student_data = recog.load_registered_students()

            send_progress(current_user.teacher_id, "🔍 Matching faces to students...", 75)
            recognized_students = recog.match_faces_to_students(valid_embeddings, student_data)
            recognized_names = [
                student.name for student in Student.query.filter(Student.student_id.in_(recognized_students)).all()
            ]
            print(f"[RESULT] Recognized Students: {recognized_names}")


            send_progress(current_user.teacher_id, "🎉 Done!", 100)

            if os.path.exists(filepath):
                os.remove(filepath)

        except Exception as e:
            send_progress(current_user.teacher_id, f"❌ Error: {str(e)}", 100)
            flash(f"Video processing failed: {str(e)}", "danger")
            return redirect(url_for('teacher.dashboard'))
    else:
        flash("Invalid file format", "danger")
        return redirect(url_for('teacher.dashboard'))

    # 🔍 Simulated ML Recognition (replace with your model) 
    # recognized_students = {1, 2, 3, 4, 7}

    # 🧠 Get full list of students from selected class

    all_students = Student.query.filter_by(class_id=class_id).all()
    students_with_flags = []
    for student in all_students:
        is_recognized = student.student_id in recognized_students
        students_with_flags.append((student, is_recognized))

    class_obj = Class.query.get(current_user.class_in_charge)
    class_name = class_obj.class_name if class_obj else "N/A"

    teacher_classes = Class.query.all()
    teacher_subjects = Subject.query.filter(
        Subject.class_id.in_([cls.class_id for cls in teacher_classes])
    ).all()

    return render_template(
        'teacher/dashboard.html',
        teacher=current_user,
        class_name=class_name,
        teacher_classes=teacher_classes,
        teacher_subjects=teacher_subjects,
        students_with_flags=students_with_flags,
        recognition_method='video',
        class_id=class_id,
        subject_id=subject_id,
        period_input=periods,
        date=date
    )


@teacher_bp.route('/get_subjects/<int:class_id>')
@login_required
@role_required('teacher')
def get_subjects(class_id):
    subjects = Subject.query.filter_by(class_id=class_id).all()
    subject_list = [{'id': subj.subject_id, 'name': subj.subject_name} for subj in subjects]
    return jsonify(subject_list)




@teacher_bp.route('/upload_csv', methods=['POST'])
@login_required
@role_required('teacher')
def upload_csv():
    if 'csv_file' not in request.files:
        flash("No file selected", "danger")
        return redirect(url_for('teacher.dashboard'))

    csv_file = request.files['csv_file']
    class_id = request.form.get('class_id')
    subject_id = request.form.get('subject_id')
    periods = request.form.get('periods')
    date = request.form.get('date')

    if not all([class_id, subject_id, periods, date]):
        flash("Missing required form data. Please select Class, Subject, Periods, and Date.", "danger")
        return redirect(url_for('teacher.dashboard'))


    if not csv_file.filename.endswith(('.csv', '.txt')):
        flash("Invalid file type. Upload .csv or .txt file", "danger")
        return redirect(url_for('teacher.dashboard'))

    content = csv_file.read().decode('utf-8').strip()
    try:
        recognized_ids = {int(id.strip()) for id in content.split(',') if id.strip().isdigit()}
    except ValueError:
        flash("Invalid file content", "danger")
        return redirect(url_for('teacher.dashboard'))

    all_students = Student.query.filter_by(class_id=class_id).all()
    students_with_flags = [(student, student.student_id in recognized_ids) for student in all_students]

    class_obj = Class.query.get(current_user.class_in_charge)
    class_name = class_obj.class_name if class_obj else "N/A"

    teacher_classes = Class.query.all()
    teacher_subjects = Subject.query.filter(
        Subject.class_id.in_([cls.class_id for cls in teacher_classes])
    ).all()

    return render_template(
        'teacher/dashboard.html',
        teacher=current_user,
        class_name=class_name,
        teacher_classes=teacher_classes,
        teacher_subjects=teacher_subjects,
        students_with_flags=students_with_flags,
        recognition_method='csv',
        class_id=class_id,
        subject_id=subject_id,
        period_input=periods,
        date=date
    )


@teacher_bp.route('/manual_attendance', methods=['POST'])
@login_required
@role_required('teacher')
def manual_attendance():
    class_id = request.form.get('class_id')
    subject_id = request.form.get('subject_id')
    periods = request.form.get('periods')
    date = request.form.get('date')

    if not all([class_id, subject_id, periods, date]):
        flash("Missing required form data. Please select Class, Subject, Periods, and Date.", "danger")
        return redirect(url_for('teacher.dashboard'))


    all_students = Student.query.filter_by(class_id=class_id).all()
    students_with_flags = [(student, False) for student in all_students]

    class_obj = Class.query.get(current_user.class_in_charge)
    class_name = class_obj.class_name if class_obj else "N/A"

    teacher_classes = Class.query.all()
    teacher_subjects = Subject.query.filter(
        Subject.class_id.in_([cls.class_id for cls in teacher_classes])
    ).all()

    return render_template(
        'teacher/dashboard.html',
        teacher=current_user,
        class_name=class_name,
        teacher_classes=teacher_classes,
        teacher_subjects=teacher_subjects,
        students_with_flags=students_with_flags,
        recognition_method='manual',
        class_id=class_id,
        subject_id=subject_id,
        period_input=periods,
        date=date
    )



@teacher_bp.route('/confirm_attendance', methods=['POST'])
@login_required
@role_required('teacher')
def confirm_attendance():
    from datetime import datetime

    class_id = request.form.get('class_id')
    subject_id = request.form.get('subject_id')
    periods = request.form.get('period')  # e.g., "1,2,3"
    date = request.form.get('date')

    present_ids = request.form.getlist('present_ids')
    period_count = len([p.strip() for p in periods.split(',') if p.strip()])

    # ✅ Log present students' attendance
    for student_id in present_ids:
        db.session.add(AttendanceLog(
            class_id=class_id,
            subject_id=subject_id,
            student_id=student_id,
            teacher_id=current_user.teacher_id,
            date=datetime.strptime(date, '%Y-%m-%d').date(),
            periods=periods
        ))

        summary = AttendanceSummary.query.filter_by(
            class_id=class_id,
            subject_id=subject_id,
            student_id=student_id
        ).first()

        if not summary:
            flash(f"❌ AttendanceSummary not found for student {student_id}. Please contact admin.", "danger")
            return redirect(url_for('teacher.attendance_history'))

        summary.classes_present += period_count

    # ✅ Update total classes for everyone
    all_students = Student.query.filter_by(class_id=class_id).all()
    for student in all_students:
        summary = AttendanceSummary.query.filter_by(
            class_id=class_id,
            subject_id=subject_id,
            student_id=student.student_id
        ).first()

        if not summary:
            flash(f"❌ AttendanceSummary missing for student {student.student_id}. Please contact admin.", "danger")
            return redirect(url_for('teacher.attendance_history'))

        summary.total_classes += period_count

    db.session.commit()
    flash("✅ Attendance confirmed and saved successfully!", "success")
    return redirect(url_for('teacher.dashboard'))



@teacher_bp.route('/attendance_history')
@login_required
@role_required('teacher')
def attendance_history():
    # Get last 5 unique attendance entries
    subquery = (
        db.session.query(
            AttendanceLog.date,
            AttendanceLog.class_id,
            AttendanceLog.subject_id,
            AttendanceLog.periods,
            AttendanceLog.video_path
        )
        .filter_by(teacher_id=current_user.teacher_id)
        .group_by(
            AttendanceLog.date,
            AttendanceLog.class_id,
            AttendanceLog.subject_id,
            AttendanceLog.periods,
            AttendanceLog.video_path
        )
        .order_by(AttendanceLog.date.desc())
        .limit(5)
        .subquery()
    )

    grouped_logs = []
    for row in db.session.query(subquery).order_by(subquery.c.date.desc()):  # ✅ Enforcing order here
        logs = AttendanceLog.query.filter_by(
            teacher_id=current_user.teacher_id,
            date=row.date,
            class_id=row.class_id,
            subject_id=row.subject_id,
            periods=row.periods
        ).all()

        class_name = Class.query.get(row.class_id).class_name
        subject_name = Subject.query.get(row.subject_id).subject_name
        students = [(log.attendance_id, log.student_id, log.student.name) for log in logs]
        student_ids = [log.student_id for log in logs]

        grouped_logs.append({
            "date": row.date,
            "class_id": row.class_id,
            "subject_id": row.subject_id,
            "periods": row.periods,
            "video_path": row.video_path,
            "class_name": class_name,
            "subject_name": subject_name,
            "students": students,
            "student_ids": student_ids
        })

    student_list = Student.query.all()
    return render_template("teacher/attendance_history.html", logs=grouped_logs, all_students=student_list)


@teacher_bp.route('/update_attendance/<date>/<int:class_id>/<int:subject_id>', methods=['POST'])
@login_required
@role_required('teacher')
def update_attendance(date, class_id, subject_id):
    from datetime import datetime

    try:
        student_id = int(request.form.get('student_id'))
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        flash("Invalid input provided.", "danger")
        return redirect(url_for('teacher.attendance_history'))

    # Use any reference log to get periods & video_path
    ref_log = AttendanceLog.query.filter_by(
        teacher_id=current_user.teacher_id,
        date=date_obj,
        class_id=class_id,
        subject_id=subject_id
    ).first()

    if not ref_log:
        flash("Attendance log reference not found.", "danger")
        return redirect(url_for('teacher.attendance_history'))

    # Add new attendance log for the student
    db.session.add(AttendanceLog(
        teacher_id=current_user.teacher_id,
        class_id=class_id,
        subject_id=subject_id,
        student_id=student_id,
        date=date_obj,
        periods=ref_log.periods,
        video_path=ref_log.video_path
    ))

    # Count the number of periods
    period_count = len([p.strip() for p in ref_log.periods.split(',') if p.strip()])

    # Update only classes_present in summary (NOT total_classes)
    summary = AttendanceSummary.query.filter_by(
        class_id=class_id, subject_id=subject_id, student_id=student_id).first()

    if summary:
        summary.classes_present += period_count
    else:
        flash("Fatal error: Attendance summary missing for this student. Contact admin.", "danger")
        return redirect(url_for('teacher.attendance_history'))

    db.session.commit()
    flash("Student added to attendance.", "success")
    return redirect(url_for('teacher.attendance_history'))



@teacher_bp.route('/attendance_stats', methods=['GET', 'POST'])
@login_required
@role_required('teacher')
def attendance_stats():
    classes = Class.query.all()
    subjects = Subject.query.all()
    selected_class = request.args.get('class_id')
    selected_subject = request.args.get('subject_id')
    search_query = request.args.get('search')

    query = db.session.query(
        AttendanceSummary,
        Student
    ).join(Student, Student.student_id == AttendanceSummary.student_id)

    if selected_class:
        query = query.filter(AttendanceSummary.class_id == selected_class)
    if selected_subject:
        query = query.filter(AttendanceSummary.subject_id == selected_subject)
    if search_query:
        query = query.filter(
            (Student.name.ilike(f"%{search_query}%")) |
            (Student.student_id == search_query)
        )

    records = query.all()

    return render_template(
        'teacher/attendance_stats.html',
        records=records,
        classes=classes,
        subjects=subjects,
        selected_class=selected_class,
        selected_subject=selected_subject,
        search_query=search_query
    )

from xhtml2pdf import pisa
from flask import render_template, make_response
import io

@teacher_bp.route('/attendance_stats/export_pdf', methods=['POST'])
@login_required
@role_required('teacher')
def export_attendance_pdf():
    selected_class = request.form.get('class_id')
    selected_subject = request.form.get('subject_id')
    search_query = request.form.get('search')

    query = db.session.query(AttendanceSummary, Student).join(Student)

    if selected_class:
        query = query.filter(AttendanceSummary.class_id == selected_class)
    if selected_subject:
        query = query.filter(AttendanceSummary.subject_id == selected_subject)
    if search_query:
        query = query.filter(
            (Student.name.ilike(f"%{search_query}%")) |
            (Student.student_id == search_query)
        )

    records = query.all()

    html = render_template('teacher/attendance_pdf.html', records=records)

    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=result)

    if pisa_status.err:
        return "Error creating PDF", 500

    response = make_response(result.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "inline; filename=attendance_report.pdf"
    return response
