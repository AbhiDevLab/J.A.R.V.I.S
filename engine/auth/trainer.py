"""
Trainer for the authentication system using Faster R-CNN for face detection
and FaceNet (InceptionResnetV1) for face embeddings. This replaces the
older Haar+LBPH approach with a modern detection+embedding pipeline.

Notes:
- Requires `torch`, `torchvision`, and `facenet-pytorch` in the environment.
- Outputs per-person averaged embeddings to `engine/auth/trainer/embeddings.pkl`.
"""

import os
import pickle
from PIL import Image
import torch
from torchvision import transforms
import torchvision
from facenet_pytorch import InceptionResnetV1


# Configuration
SAMPLES_PATH = os.path.join('engine', 'auth', 'samples')
OUTPUT_PATH = os.path.join('engine', 'auth', 'trainer')
EMBEDDINGS_FILE = os.path.join(OUTPUT_PATH, 'embeddings.pkl')

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


def load_detection_model():
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)
    model.to(device).eval()
    return model


def detect_faces_pil(model, pil_img, threshold=0.8):
    """Run Faster R-CNN on a PIL image and return list of bounding boxes (x1,y1,x2,y2).
    Boxes are in pixel coordinates on the original image."""
    transform = transforms.ToTensor()
    img_t = transform(pil_img).to(device)
    with torch.no_grad():
        outputs = model([img_t])
    out = outputs[0]
    boxes = out['boxes']
    scores = out['scores']
    sel = scores >= threshold
    boxes = boxes[sel].cpu().numpy()
    # convert boxes to tuples
    boxes = [tuple(map(int, b)) for b in boxes]
    return boxes


def preprocess_for_facenet(pil_face):
    # Resize to 160x160 and normalize to [-1,1]
    trans = transforms.Compose([
        transforms.Resize((160, 160)),
        transforms.ToTensor(),
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
    ])
    return trans(pil_face).to(device)


def train_embeddings(samples_path=SAMPLES_PATH, out_file=EMBEDDINGS_FILE, detect_threshold=0.8):
    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    det_model = load_detection_model()
    rec_model = InceptionResnetV1(pretrained='vggface2').eval().to(device)

    embeddings_per_id = {}

    image_files = [os.path.join(samples_path, f) for f in os.listdir(samples_path) if os.path.isfile(os.path.join(samples_path, f))]

    print('Found', len(image_files), 'sample images.')

    for img_path in image_files:
        try:
            pil_img = Image.open(img_path).convert('RGB')
        except Exception as e:
            print('Skipping', img_path, '— failed to open:', e)
            continue

        # Expect filenames like <name>.<id>.<ext> (keeps compatibility with previous pipeline)
        basename = os.path.split(img_path)[-1]
        parts = basename.split('.')
        if len(parts) < 2:
            print('Skipping', img_path, '— unexpected filename format')
            continue
        try:
            person_id = int(parts[1])
        except ValueError:
            print('Skipping', img_path, '— cannot parse ID from filename')
            continue

        boxes = detect_faces_pil(det_model, pil_img, threshold=detect_threshold)
        if not boxes:
            print('No face found in', img_path)
            continue

        # Use the largest box if multiple detections
        boxes_sorted = sorted(boxes, key=lambda b: (b[2]-b[0])*(b[3]-b[1]), reverse=True)
        box = boxes_sorted[0]
        x1, y1, x2, y2 = box
        face_crop = pil_img.crop((x1, y1, x2, y2))

        try:
            face_t = preprocess_for_facenet(face_crop)
            with torch.no_grad():
                emb = rec_model(face_t.unsqueeze(0)).cpu().numpy()[0]
        except Exception as e:
            print('Embedding error for', img_path, e)
            continue

        embeddings_per_id.setdefault(person_id, []).append(emb)

    # Average embeddings per person and save
    averaged = {pid: (sum(lst) / len(lst)).tolist() for pid, lst in embeddings_per_id.items()}

    with open(out_file, 'wb') as f:
        pickle.dump(averaged, f)

    print(f'Training complete — saved {len(averaged)} embeddings to', out_file)


if __name__ == '__main__':
    print('Training embeddings pipeline — this may take a while depending on hardware.')
    train_embeddings()