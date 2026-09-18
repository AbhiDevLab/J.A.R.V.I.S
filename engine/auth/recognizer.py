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
import base64
from PIL import Image
import numpy as np
import torch
from torchvision import transforms
import torchvision
from facenet_pytorch import InceptionResnetV1, MTCNN


EMBEDDINGS_FILE = os.path.join('engine', 'auth', 'trainer', 'embeddings.pkl')
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
_DET_MODEL = None
_REC_MODEL = None
_MTCNN = None
_GALLERY = None


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

def get_runtime_models_and_gallery():
    global _DET_MODEL
    global _REC_MODEL
    global _MTCNN
    global _GALLERY

    if _DET_MODEL is None:
        print("Loading face detection model...")
        _DET_MODEL = torchvision.models.detection.fasterrcnn_resnet50_fpn(
            pretrained=True
        )
        _DET_MODEL.to(device).eval()

    if _REC_MODEL is None:
        print("Loading FaceNet model...")
        _REC_MODEL = InceptionResnetV1(
            pretrained='vggface2'
        ).eval().to(device)

    if _MTCNN is None:
        _MTCNN = MTCNN(
            keep_all=False,
            device=device
        )

    if _GALLERY is None:
        print("Loading face embedding gallery...")
        _GALLERY = load_embeddings()

    return _DET_MODEL, _REC_MODEL, _MTCNN, _GALLERY


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
    det_model, rec_model, mtcnn, gallery = get_runtime_models_and_gallery()

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
                     overlay_seconds: float | None = None,
                     frame_callback=None) -> int:
    """Open the existing OpenCV webcam and authenticate the user.

    The webcam used here is also streamed to the Eel frontend through
    ``frame_callback``. The browser therefore displays the exact camera feed
    that is being used by the face-recognition pipeline.

    Returns:
        1 on successful authentication.
        0 on authentication failure or camera failure.

    Environment variables:
        JARVIS_AUTH_ID (int)
        JARVIS_AUTH_FRAMES (int)
        JARVIS_AUTH_TIMEOUT (int)
        JARVIS_AUTH_THRESHOLD (float, 0-1)
        JARVIS_AUTH_OVERLAY_SECONDS (float)
        JARVIS_AUTH_WEBCAM_FPS (int)
    """
    try:
        import cv2
    except Exception as e:
        print('AuthenticateFace: missing OpenCV dependency', e)
        return 0

    # ------------------------------------------------------------------
    # Load configurable defaults from environment.
    # ------------------------------------------------------------------
    try:
        if allowed_id is None:
            allowed_id = int(os.getenv('JARVIS_AUTH_ID', '1'))
    except Exception:
        allowed_id = 1

    try:
        if required_consecutive is None:
            required_consecutive = int(
                os.getenv('JARVIS_AUTH_FRAMES', '3')
            )
    except Exception:
        required_consecutive = 3

    try:
        if timeout is None:
            timeout = int(
                os.getenv('JARVIS_AUTH_TIMEOUT', '20')
            )
    except Exception:
        timeout = 20

    try:
        if threshold is None:
            threshold = float(
                os.getenv('JARVIS_AUTH_THRESHOLD', '0.9')
            )
    except Exception:
        threshold = 0.9

    # Kept for compatibility with the previous AuthenticateFace() API.
    try:
        if overlay_seconds is None:
            overlay_seconds = float(
                os.getenv('JARVIS_AUTH_OVERLAY_SECONDS', '4')
            )
    except Exception:
        overlay_seconds = 4.0

    # Number of webcam frames per second sent to the browser.
    try:
        webcam_fps = max(
            1,
            int(os.getenv('JARVIS_AUTH_WEBCAM_FPS', '15'))
        )
    except Exception:
        webcam_fps = 15

    preview_interval = 1.0 / webcam_fps
    last_preview_time = 0.0

    # ------------------------------------------------------------------
    # Open the same webcam that the recognizer owns.
    # ------------------------------------------------------------------
    try:
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(0)
    except Exception as e:
        print('Camera initialization error:', e)
        cap = None

    if cap is None or not cap.isOpened():
        print('Camera not available')

        if frame_callback is not None:
            try:
                frame_callback(
                    '',
                    'Camera not available',
                    None
                )
            except Exception as e:
                print('Webcam UI update error:', e)

        return 0

    positives = 0
    start = time.time()
    last_frame = None
    last_jpg_base64 = ''
    frame_count = 0

    # Recognition is much more expensive than grabbing/displaying a frame.
    # Run recognition once every 3 frames while keeping the camera preview
    # smooth.
    process_every = 3

    print('Starting face authentication...')
    print(f'Required consecutive frames: {required_consecutive}')
    print(f'Threshold: {threshold}')
    print(f'Timeout: {timeout}s')
    print(f'Webcam preview FPS: {webcam_fps}')

    try:
        while time.time() - start < timeout:
            ret, frame = cap.read()

            if not ret:
                continue

            last_frame = frame.copy()
            frame_count += 1

            # ----------------------------------------------------------
            # Stream the real OpenCV frame to the Eel frontend.
            # ----------------------------------------------------------
            now = time.time()

            if (
                frame_callback is not None
                and now - last_preview_time >= preview_interval
            ):
                try:
                    ok, buffer = cv2.imencode(
                        '.jpg',
                        frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 75]
                    )

                    if ok:
                        last_jpg_base64 = base64.b64encode(
                            buffer
                        ).decode('utf-8')

                        frame_callback(
                            last_jpg_base64,
                            'Scanning face...',
                            None
                        )

                        last_preview_time = now

                except Exception as e:
                    print(f'Frame callback error: {e}')

            # ----------------------------------------------------------
            # Do not run the expensive recognition model on every frame.
            # ----------------------------------------------------------
            if frame_count % process_every != 0:
                continue

            pil = Image.fromarray(
                cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            )

            try:
                res = recognize_image(
                    pil,
                    threshold=threshold
                )
            except Exception as e:
                print('Recognition error:', e)
                res = None

            # ----------------------------------------------------------
            # Valid identity match.
            # ----------------------------------------------------------
            if res and res.get('id') == allowed_id:
                positives += 1

                score = float(res.get('score', 0.0))

                print(
                    f'Positive frame '
                    f'{positives}/{required_consecutive} '
                    f'(score={score:.3f})'
                )

                # Send a recognition frame with the detected face box.
                if frame_callback is not None:
                    try:
                        display_frame = frame.copy()

                        box = res.get('box')

                        if box:
                            x1, y1, x2, y2 = map(int, box)

                            cv2.rectangle(
                                display_frame,
                                (x1, y1),
                                (x2, y2),
                                (0, 200, 0),
                                2
                            )

                        ok, buffer = cv2.imencode(
                            '.jpg',
                            display_frame,
                            [cv2.IMWRITE_JPEG_QUALITY, 75]
                        )

                        if ok:
                            last_jpg_base64 = base64.b64encode(
                                buffer
                            ).decode('utf-8')

                            frame_callback(
                                last_jpg_base64,
                                (
                                    f'Face recognized '
                                    f'({positives}/{required_consecutive})'
                                ),
                                score
                            )

                            last_preview_time = time.time()

                    except Exception as e:
                        print(
                            f'Recognition UI update error: {e}'
                        )

                # ------------------------------------------------------
                # Authentication succeeds after the required number of
                # consecutive positive frames.
                # ------------------------------------------------------
                if positives >= required_consecutive:
                    if frame_callback is not None:
                        try:
                            if not last_jpg_base64:
                                ok, buffer = cv2.imencode(
                                    '.jpg',
                                    frame,
                                    [cv2.IMWRITE_JPEG_QUALITY, 75]
                                )

                                if ok:
                                    last_jpg_base64 = base64.b64encode(
                                        buffer
                                    ).decode('utf-8')

                            frame_callback(
                                last_jpg_base64,
                                'Authenticated',
                                score
                            )

                        except Exception as e:
                            print(
                                f'Authentication UI update error: {e}'
                            )

                    cap.release()
                    print('✓ ACCESS GRANTED')
                    return 1

            # ----------------------------------------------------------
            # No valid match.
            # ----------------------------------------------------------
            else:
                positives = 0

                if frame_callback is not None:
                    try:
                        frame_callback(
                            last_jpg_base64,
                            'Face not recognized',
                            None
                        )
                    except Exception as e:
                        print(
                            f'Recognition UI update error: {e}'
                        )

            # Prevent a tight CPU loop.
            time.sleep(0.01)

    finally:
        # Always release the same OpenCV camera when authentication exits.
        try:
            cap.release()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Authentication timed out.
    # No separate cv2.imshow() window is opened here because the Eel
    # frontend is the authentication UI.
    # ------------------------------------------------------------------
    if frame_callback is not None:
        try:
            if not last_jpg_base64 and last_frame is not None:
                ok, buffer = cv2.imencode(
                    '.jpg',
                    last_frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 75]
                )

                if ok:
                    last_jpg_base64 = base64.b64encode(
                        buffer
                    ).decode('utf-8')

            frame_callback(
                last_jpg_base64,
                'Authentication timed out',
                None
            )

        except Exception as e:
            print(f'Final webcam update error: {e}')

    print('✗ ACCESS DENIED - Accuracy too low or timeout')
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
