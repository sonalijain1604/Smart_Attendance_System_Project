import cv2
from deepface import DeepFace
import numpy as np
from scipy.spatial.distance import cosine
from mtcnn import MTCNN
from app.models import StudentEmbedding

def extract_faces(video_path: str, frame_interval: int = 5) -> list:
    """
    Extract faces from the given video using MTCNN at specified frame intervals.
    """
    face_detector = MTCNN()
    video_capture = cv2.VideoCapture(video_path)
    extracted_faces = []
    frame_index = 0

    while True:
        success, frame = video_capture.read()
        if not success:
            break

        if frame_index % frame_interval == 0:
            detected_faces = face_detector.detect_faces(frame)
            for face_data in detected_faces:
                x, y, width, height = face_data['box']
                face_image = frame[y:y+height, x:x+width]
                extracted_faces.append(face_image)

        frame_index += 1

    video_capture.release()
    return extracted_faces

def generate_face_embedding(face_image: np.ndarray) -> np.ndarray | None:
    """
    Generate face embedding using DeepFace with the Facenet model.
    """
    try:
        result = DeepFace.represent(face_image, model_name="Facenet", enforce_detection=False)
        return result[0]['embedding']
    except Exception as e:
        print(f"[ERROR] Failed to generate embedding: {e}")
        return None

def load_registered_students() -> dict[int, np.ndarray]:
    """
    Loads all registered student embeddings from the database.
    Returns a dictionary mapping student_id to their corresponding embedding array.
    """
    student_embeddings = {}

    all_records = StudentEmbedding.query.all()

    for record in all_records:
        embedding_array = np.frombuffer(record.embedding, dtype=np.float32)

        if embedding_array.shape != (128,):
            print(f"[WARNING] Embedding for student ID {record.student_id} has invalid shape: {embedding_array.shape}")
            continue

        student_embeddings[record.student_id] = embedding_array

    print(f"[INFO] Loaded {len(student_embeddings)} student embeddings.")
    return student_embeddings


def match_faces_to_students(video_face_embeddings: list, registered_embeddings: dict, similarity_threshold: float = 0.6) -> set:
    """
    Match extracted face embeddings to registered students using cosine similarity.
    Modified: Assign detected faces to best matching student if above threshold.
    """
    identified_students = set() 

    for embedding in video_face_embeddings:
        best_match_id = None
        best_similarity = -1

        for student_id, student_embedding in registered_embeddings.items():
            if student_embedding.shape != (128,):
                print(f"[WARNING] Skipping {student_id}: Invalid embedding shape {student_embedding.shape}")
                continue

            similarity = 1 - cosine(student_embedding, embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_id = student_id

        print(f"[DEBUG] Best Match: {best_match_id} with similarity {best_similarity:.3f}")

        if best_similarity >= similarity_threshold:
            identified_students.add(best_match_id)
            print(f"[INFO] Recognized: {best_match_id}")

    return identified_students


def recognize_students_in_video(video_path: str) -> set:
    """
    Full pipeline to recognize students in a given video.
    """
    print("[STEP 1] Extracting faces from video...")
    detected_faces = extract_faces(video_path)
    print(f"[INFO] Extracted {len(detected_faces)} faces.")

    print("[STEP 2] Generating embeddings...")
    embeddings = [generate_face_embedding(face) for face in detected_faces]
    valid_embeddings = [emb for emb in embeddings if emb is not None]
    print(f"[INFO] Generated {len(valid_embeddings)} valid embeddings.")

    if not valid_embeddings:
        print("[ERROR] No valid embeddings were found. Exiting.")
        return set()

    print("[STEP 3] Loading registered students...")
    student_data = load_registered_students()

    print("[STEP 4] Matching faces to students...")
    recognized = match_faces_to_students(valid_embeddings, student_data)

    print(f"[RESULT] Recognized Students: {recognized}")
    return recognized

