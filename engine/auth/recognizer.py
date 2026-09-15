"""
Runtime recognizer using Faster R-CNN for detection and FaceNet for embeddings.
Loads averaged embeddings produced by `trainer.py` and compares gallery
embeddings with cosine similarity.

Usage: import `recognize_image` and pass a PIL image, or run as script to
attempt recognition from a webcam feed.
"""

import os
import pickle
import time
from PIL import Image
import numpy as np
import torch
from torchvision import transforms
import torchvision
from facenet_pytorch import InceptionResnetV1, MTCNN


EMBEDDINGS_FILE = os.path.join('engine', 'auth', 'trainer', 'embeddings.pkl')
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def load_models(device=device):
    det_model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)
    det_model.to(device).eval()
    rec_model = InceptionResnetV1(pretrained='vggface2').eval().to(device)
    # MTCNN used only for landmarks on the detected crop
    mtcnn = MTCNN(keep_all=False, device=device)
    return det_model, rec_model, mtcnn


def load_embeddings(path=EMBEDDINGS_FILE):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, 'rb') as f:
        embeddings = pickle.load(f)
    # convert to numpy arrays
    emb_map = {int(k): np.array(v) for k, v in embeddings.items()}
    return emb_map


def preprocess_for_facenet(pil_face):
    trans = transforms.Compose([
        transforms.Resize((160, 160)),
        transforms.ToTensor(),
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
    ])
    return trans(pil_face).to(device)


def cosine_similarity(a, b):
    a_norm = a / np.linalg.norm(a)
    b_norm = b / np.linalg.norm(b)
    return float(np.dot(a_norm, b_norm))


def recognize_image(pil_img, top_k=1, threshold=0.6):
    det_model, rec_model, mtcnn = load_models()
    gallery = load_embeddings()

    # detect
    transform = transforms.ToTensor()
    img_t = transform(pil_img).to(device)
    with torch.no_grad():
        out = det_model([img_t])[0]
    scores = out['scores'].cpu().numpy()
    boxes = out['boxes'].cpu().numpy()
    # choose best box above score threshold
    if len(scores) == 0 or scores.max() < 0.8:
        return None
    best_idx = int(scores.argmax())
    x1, y1, x2, y2 = map(int, boxes[best_idx])
    face_crop = pil_img.crop((x1, y1, x2, y2))

    # landmarks (optional)
    try:
        boxes_mt, probs = mtcnn.detect(face_crop)
        landmarks = None
        if boxes_mt is not None and len(boxes_mt) > 0:
            # mtcnn.detect on a crop returns coordinates relative to crop
            landmarks = mtcnn.detect(face_crop)[0]
    except Exception:
        landmarks = None

    # embedding
    face_t = preprocess_for_facenet(face_crop)
    with torch.no_grad():
        emb = rec_model(face_t.unsqueeze(0)).cpu().numpy()[0]

    # compare to gallery
    scores = []
    for pid, g_emb in gallery.items():
        sim = cosine_similarity(emb, g_emb)
        scores.append((pid, sim))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)

    best_pid, best_sim = scores[0]
    if best_sim < threshold:
        return None

    return {
        'id': int(best_pid),
        'score': float(best_sim),
        'box': (x1, y1, x2, y2),
        'landmarks': landmarks,
    }


def AuthenticateFace(required_consecutive: int | None = None,
                     timeout: int | None = None,
                     threshold: float | None = None,
                     allowed_id: int | None = None,
                     overlay_seconds: float | None = None) -> int:
    """Compatibility wrapper: open webcam and require consecutive positive frames.
    Reads defaults from environment variables when parameters are not provided.
    Returns 1 on success, 0 on failure. Matches old `AuthenticateFace()` API.
    Env vars supported:
      - JARVIS_AUTH_ID (int)
      - JARVIS_AUTH_FRAMES (int)
      - JARVIS_AUTH_TIMEOUT (int)
      - JARVIS_AUTH_THRESHOLD (float, 0-1)
      - JARVIS_AUTH_OVERLAY_SECONDS (float)
    """
    try:
        import cv2
        from PIL import Image
    except Exception as e:
        print('AuthenticateFace: missing dependency', e)
        return 0

    # load configurable defaults from environment when parameters are not provided
    try:
        if allowed_id is None:
            allowed_id = int(os.getenv('JARVIS_AUTH_ID', '1'))
    except Exception:
        allowed_id = 1

    try:
        if required_consecutive is None:
            required_consecutive = int(os.getenv('JARVIS_AUTH_FRAMES', '3'))
    except Exception:
        required_consecutive = 3

    try:
        if timeout is None:
            timeout = int(os.getenv('JARVIS_AUTH_TIMEOUT', '20'))
    except Exception:
        timeout = 20

    try:
        if threshold is None:
            # default to 0.9 (90%) as requested; allow override via env
            threshold = float(os.getenv('JARVIS_AUTH_THRESHOLD', '0.9'))
    except Exception:
        threshold = 0.9

    try:
        if overlay_seconds is None:
            overlay_seconds = float(os.getenv('JARVIS_AUTH_OVERLAY_SECONDS', '4'))
    except Exception:
        overlay_seconds = 4.0

    # open camera
    try:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)
    except Exception:
        cap = None

    if cap is None or not cap.isOpened():
        print('Camera not available')
        return 0

    positives = 0
    start = time.time()
    last_frame = None
    last_res = None

    while time.time() - start < timeout:
        ret, frame = cap.read()
        if not ret:
            continue
        last_frame = frame.copy()
        pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        try:
            res = recognize_image(pil, threshold=threshold)
        except Exception as e:
            print('Recognition error:', e)
            res = None

        last_res = res

        if res and res.get('id') == allowed_id:
            positives += 1
            print(f'Positive frame {positives}/{required_consecutive} (score={res.get("score"):.2f})')
            if positives >= required_consecutive:
                # show authenticated overlay for configured seconds
                box = res.get('box')
                show_overlay_and_wait(last_frame, box, 'Authenticated', color=(0, 200, 0), seconds=overlay_seconds)
                cap.release()
                print('\u2713 ACCESS GRANTED')
                return 1
        else:
            positives = 0

        # small delay to avoid busy-loop
        cv2.waitKey(50)

    # timed out - show unauthenticated overlay using last detection if available
    if last_frame is not None:
        box = last_res.get('box') if last_res else None
        show_overlay_and_wait(last_frame, box, 'Unauthenticated', color=(0, 0, 200), seconds=overlay_seconds)

    cap.release()
    print('\u2717 ACCESS DENIED - Accuracy too low or timeout')
    return 0


def show_overlay_and_wait(frame, box, text, color=(0, 255, 0), seconds=4):
    """Draw box and centered text on frame and display for `seconds` seconds."""
    try:
        import cv2 as _cv
    except Exception:
        return

    overlay = frame.copy()
    h, w = overlay.shape[:2]
    if box:
        x1, y1, x2, y2 = box
        _cv.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
    # draw semi-transparent banner
    banner_h = 60
    _cv.rectangle(overlay, (0, h - banner_h), (w, h), (0, 0, 0), -1)
    alpha = 0.6
    _cv.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    # text
    _cv.putText(frame, text, (10, h - 20), _cv.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

    win = 'Authentication'
    _cv.imshow(win, frame)
    # wait for seconds, but keep window responsive
    t0 = time.time()
    while time.time() - t0 < seconds:
        if _cv.waitKey(100) & 0xFF == ord('q'):
            break
    _cv.destroyWindow(win)


if __name__ == '__main__':
    # Quick webcam demo
    try:
        import cv2
    except Exception:
        print('OpenCV is required for webcam demo')
        raise

    det_model, rec_model, mtcnn = load_models()
    gallery = load_embeddings()

    cap = cv2.VideoCapture(0)
    print('Press q to quit')
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        res = recognize_image(pil)
        if res is not None:
            x1, y1, x2, y2 = res['box']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"ID:{res['id']} {res['score']:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow('recognizer', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()
