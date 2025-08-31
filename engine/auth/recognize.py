from sys import flags
import time
import cv2
import pyautogui as p

def AuthenticateFace():
    # Local Binary Patterns Histograms
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read('engine\\auth\\trainer\\trainer.yml')  # load trained model
    cascadePath = "engine\\auth\\haarcascade_frontalface_default.xml"
    faceCascade = cv2.CascadeClassifier(cascadePath)
    font = cv2.FONT_HERSHEY_SIMPLEX

    id = 2
    names = ['', 'Abhi']

    # Set minimum accuracy threshold (50% or higher)
    MIN_ACCURACY_THRESHOLD = 50  # Only accept recognitions with 50%+ accuracy

    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cam.set(3, 640)
    cam.set(4, 480)

    minW = 0.1 * cam.get(3)
    minH = 0.1 * cam.get(4)

    # Variables for tracking authentication
    authenticated = False
    confidence_scores = []  # Store confidence scores for multiple frames
    required_confidence_frames = 5  # Number of consecutive frames with good confidence
    
    print("Starting face authentication...")
    print(f"Minimum accuracy required: {MIN_ACCURACY_THRESHOLD}%")

    while True:
        ret, img = cam.read()
        if not ret:
            break

        converted_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Apply image enhancement for better recognition
        converted_image = cv2.equalizeHist(converted_image)  # Improve contrast

        faces = faceCascade.detectMultiScale(
            converted_image,
            scaleFactor=1.2,
            minNeighbors=5,
            minSize=(int(minW), int(minH)),
        )

        frame_authenticated = False
        current_accuracy = 0
        
        for (x, y, w, h) in faces:
            # Ensure reasonable face size
            if w < 50 or h < 50:
                continue

            cv2.rectangle(img, (x, y), (x+w, y+h), (0, 255, 0), 2)

            # Get prediction
            id, confidence = recognizer.predict(converted_image[y:y+h, x:x+w])
            
            # Calculate accuracy percentage (LBPH: lower confidence = better)
            accuracy_percentage = max(0, 100 - confidence)
            
            # Check if accuracy meets the threshold
            if accuracy_percentage >= MIN_ACCURACY_THRESHOLD:
                id_name = names[id]
                accuracy_text = "  {0}%".format(round(accuracy_percentage))
                color = (0, 255, 0)  # Green for high accuracy
                frame_authenticated = True
                current_accuracy = accuracy_percentage
            else:
                id_name = "unknown"
                accuracy_text = "  {0}%".format(round(accuracy_percentage))
                color = (0, 0, 255)  # Red for low accuracy
                frame_authenticated = False

            # Display recognition info
            cv2.putText(img, str(id_name), (x+5, y-5), font, 1, (255, 255, 255), 2)
            cv2.putText(img, accuracy_text, (x+5, y+h-5), font, 1, color, 1)

            # Add debug info
            cv2.putText(img, f"Threshold: {MIN_ACCURACY_THRESHOLD}%", (10, 30), font, 0.7, (255, 255, 255), 2)
            status = "Authenticated" if frame_authenticated else "Not Authenticated"
            cv2.putText(img, f"Status: {status}", (10, 60), font, 0.7, color, 2)

        # Track multiple frames for reliable authentication
        if frame_authenticated:
            confidence_scores.append(current_accuracy)
            # Require multiple consecutive frames with good confidence
            if len(confidence_scores) >= required_confidence_frames:
                avg_accuracy = sum(confidence_scores) / len(confidence_scores)
                print(f"Authentication successful! Average accuracy: {avg_accuracy:.1f}%")
                authenticated = True
                break
        else:
            confidence_scores = []  # Reset if authentication fails in any frame

        cv2.imshow('Face Authentication - Press ESC to exit', img)

        k = cv2.waitKey(10) & 0xff
        if k == 27:
            break

    cam.release()
    cv2.destroyAllWindows()
    
    # Final authentication decision
    if authenticated:
        print("✓ ACCESS GRANTED")
        return 1
    else:
        print("✗ ACCESS DENIED - Accuracy too low")
        return 0

# For testing
if __name__ == "__main__":
    AuthenticateFace()