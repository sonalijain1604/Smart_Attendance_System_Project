# student.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
import os
from app import db
from app.models import Student, AttendanceSummary, Subject
from app.routes import role_required
import numpy as np
import json
from flask import Response, stream_with_context
import queue
from datetime import datetime
import pytz
student_bp = Blueprint('student', __name__, url_prefix='/student')

UPLOAD_FOLDER = 'app/static/uploads/student_videos'
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov'}

def allowed_video_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


@student_bp.route('/dashboard')
@login_required
@role_required('student')
def dashboard():
    if not isinstance(current_user, Student):
        flash("Access denied!", "danger")
        return redirect(url_for('auth.login'))
    # Fetch attendance summary for the student
    attendance_stats = (
        db.session.query(AttendanceSummary, Subject)
        .join(Subject, AttendanceSummary.subject_id == Subject.subject_id)
        .filter(AttendanceSummary.student_id == current_user.student_id)
        .all()
    )

    # Convert upload datetime to IST and format it
    formatted_time = None
    if current_user.last_video_uploaded_at:
        ist = pytz.timezone("Asia/Kolkata")
        local_dt = current_user.last_video_uploaded_at.astimezone(ist)
        formatted_time = local_dt.strftime("%d %B %Y, %I:%M %p")  # e.g., 20 April 2025, 05:20 PM

    return render_template(
        'student/dashboard.html',
        student=current_user,
        attendance_stats=attendance_stats,
        last_uploaded_time=formatted_time
    )

client_queues = {}

@student_bp.route('/upload_video_progress')
@login_required
@role_required('student')
def upload_video_progress():
    student_id = current_user.student_id
    q = queue.Queue()
    client_queues[student_id] = q 

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

def send_progress(student_id, step, percent):
    if student_id in client_queues:
        update = {'step': step, 'percent': percent}
        client_queues[student_id].put(json.dumps(update))
        if percent == 100:
            del client_queues[student_id]


@student_bp.route('/upload_video', methods=['POST'])
@login_required
@role_required('student')
def upload_video():
    if 'video' not in request.files:
        flash("No file part", "danger")
        return redirect(url_for('student.dashboard'))

    video = request.files['video']

    if video.filename == '':
        flash("No selected file", "danger")
        return redirect(url_for('student.dashboard'))

    if video and allowed_video_file(video.filename):
        filename = f"{current_user.student_id}_mp4"
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        video.save(filepath)

        send_progress(current_user.student_id, "📥 Video uploaded successfully", 5)
        try:
            import app.ml.register as reg

            send_progress(current_user.student_id, "🎞️ Extracting frames from video...", 25)
            frames = reg.extract_video_frames(filepath)

            send_progress(current_user.student_id, "🔍 Detecting faces in frames...", 55)
            faces = reg.detect_faces_from_frames(frames)

            send_progress(current_user.student_id, "🧠 Generating face embeddings...", 75)
            embeddings = [reg.generate_face_embedding(face) for face in faces if face is not None]
            embeddings = [e for e in embeddings if e is not None]

            if not embeddings:
                send_progress(current_user.student_id, "❌ No valid face embeddings found. Please try again.", 100)
                flash("No valid face embeddings found. Please try again.", "danger")
                return redirect(url_for('student.dashboard'))

            send_progress(current_user.student_id, "📊 Calculating average embedding...", 90)
            average_embedding = np.mean(embeddings, axis=0)

            send_progress(current_user.student_id, "💾 Saving data to database...", 95)
            reg.save_student_embedding(current_user.student_id, average_embedding)

            # ✅ Save upload info in IST
            ist = pytz.timezone('Asia/Kolkata')
            current_user.last_video_uploaded_at = datetime.now(ist)
            db.session.commit()

            if os.path.exists(filepath):
                os.remove(filepath)

            send_progress(current_user.student_id, "✅ Registration complete! You're all set.", 100)
            
            return redirect(url_for('student.dashboard'))

        except Exception as e:
            send_progress(current_user.student_id, f"❌ Registration failed: {str(e)}", 100)
            flash(f"Registration failed: {str(e)}", "danger")
            return redirect(url_for('student.upload_video'))

    else:
        flash("Invalid file format.", "danger")
        return redirect(url_for('student.upload_video'))

