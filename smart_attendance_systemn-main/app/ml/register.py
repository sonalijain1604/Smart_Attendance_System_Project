import cv2
import numpy as np
from mtcnn import MTCNN
from deepface import DeepFace

from app import db
from app.models import Student, StudentEmbedding

def extract_video_frames(video_path: str, frame_interval: int = 5) -> list:
    """
    Extracts frames from a video at specified intervals.
    """
    video_capture = cv2.VideoCapture(video_path)
    frames = []
    frame_index = 0

    while video_capture.isOpened():
        success, frame = video_capture.read()
        if not success:
            break
        if frame_index % frame_interval == 0:
            frames.append(frame)
        frame_index += 1

    video_capture.release()
    return frames

def detect_faces_from_frames(frames: list) -> list:
    """
    Detects faces in each frame using MTCNN and returns cropped face images.
    """
    face_detector = MTCNN()
    cropped_faces = []

    for frame in frames:
        detections = face_detector.detect_faces(frame)
        for detection in detections:
            x, y, width, height = detection['box']
            face = frame[y:y+height, x:x+width]
            cropped_faces.append(face)

    return cropped_faces

def generate_face_embedding(face_image: np.ndarray) -> np.ndarray | None:
    """
    Converts a face image to a DeepFace embedding using the Facenet model.
    """
    try:
        face_rgb = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
        result = DeepFace.represent(face_rgb, model_name="Facenet", enforce_detection=False)
        if result:
            return np.array(result[0]["embedding"])
        print("[WARNING] No embedding extracted for a face.")
        return None
    except Exception as error:
        print(f"[ERROR] Failed to process face: {error}")
        return None

def save_student_embedding(student_id: int, embedding: np.ndarray) -> None:
    """
    Stores or updates a student's face embedding in the database.
    """
    if embedding.shape != (128,):
        print(f"[ERROR] Invalid embedding shape: {embedding.shape}, expected (128,)")
        return

    student = Student.query.get(student_id)
    if not student:
        print(f"[ERROR] No student found with ID {student_id}")
        return

    embedding_blob = embedding.astype(np.float32).tobytes()

    existing_record = StudentEmbedding.query.filter_by(student_id=student_id).first()
    if existing_record:
        existing_record.embedding = embedding_blob
        print(f"[INFO] Updated embedding for student ID {student_id}")
    else:
        new_record = StudentEmbedding(student_id=student_id, embedding=embedding_blob)
        db.session.add(new_record)
        print(f"[INFO] Stored new embedding for student ID {student_id}")

    db.session.commit()

def list_registered_students() -> list:
    """
    Retrieves the names of all students with stored embeddings.
    """
    return [entry.student.name for entry in StudentEmbedding.query.all()]

def register_student_from_video(student_id: int, video_path: str) -> None:
    """
    Registers a student by extracting face embeddings from a video.
    """
    print(f"[PROCESS] Registering student ID {student_id} from video: {video_path}")

    frames = extract_video_frames(video_path)
    faces = detect_faces_from_frames(frames)
    print(f"[INFO] Extracted {len(faces)} faces from the video.")

    embeddings = [generate_face_embedding(face) for face in faces if face is not None]
    embeddings = [e for e in embeddings if e is not None]

    if not embeddings:
        print("[ERROR] No valid embeddings were extracted.")
        return

    average_embedding = np.mean(embeddings, axis=0)
    print(f"[INFO] Average embedding shape: {average_embedding.shape}")

    save_student_embedding(student_id, average_embedding)

    registered_students = list_registered_students()
    print(f"[INFO] Registered Students: {registered_students}")
