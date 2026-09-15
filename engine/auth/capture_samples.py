"""Capture face samples from the webcam and save to `engine/auth/samples`.

Filename format used by the trainer: <label>.<id>.<seq>.jpg
Example: Abhi.1.01.jpg

Run:
    python engine/auth/capture_samples.py --label Abhi --id 1 --count 50
"""
import os
import argparse
import time
import cv2


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--label', required=True, help='Label/name for the person (used in filename)')
    p.add_argument('--id', required=True, type=int, help='Numeric id for the person (second token in filename)')
    p.add_argument('--count', type=int, default=50, help='Number of samples to capture')
    p.add_argument('--outdir', default=os.path.join('engine', 'auth', 'samples'), help='Directory to save samples')
    p.add_argument('--delay', type=float, default=0.4, help='Delay between saved frames (seconds)')
    return p.parse_args()


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    cascade_path = os.path.join('engine', 'auth', 'haarcascade_frontalface_default.xml')
    face_cascade = cv2.CascadeClassifier(cascade_path)

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    print('Press q to stop early')

    saved = 0
    seq = 1
    last_save = 0

    while saved < args.count:
        ret, frame = cap.read()
        if not ret:
            print('Failed to read from camera')
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(80, 80))

        # draw and possibly save largest face
        if len(faces) > 0:
            # pick largest
            faces = sorted(faces, key=lambda r: r[2]*r[3], reverse=True)
            (x, y, w, h) = faces[0]
            # add small margin
            pad = int(0.2 * max(w, h))
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(frame.shape[1], x + w + pad)
            y2 = min(frame.shape[0], y + h + pad)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            now = time.time()
            if now - last_save >= args.delay:
                crop = frame[y1:y2, x1:x2]
                fname = f"{args.label}.{args.id}.{seq:02d}.jpg"
                fpath = os.path.join(args.outdir, fname)
                cv2.imwrite(fpath, crop)
                saved += 1
                seq += 1
                last_save = now
                print(f'Saved {saved}/{args.count}: {fpath}')

        # overlay status
        cv2.putText(frame, f"Saved: {saved}/{args.count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imshow('Capture Samples - Press q to quit', frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print('Done')


if __name__ == '__main__':
    main()
