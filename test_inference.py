import cv2
from ultralytics import YOLO

def test_inference(model_path, video_path):
    print(f"Loading model from {model_path}...")
    model = YOLO(model_path)
    
    print(f"Opening video {video_path}...")
    cap = cv2.VideoCapture(video_path)
    
    ret, frame = cap.read()
    if not ret:
        print("Failed to read frame")
        return
        
    print("Running inference on first frame...")
    results = model.predict(frame)
    
    if len(results) > 0:
        result = results[0]
        boxes = result.boxes
        print(f"Number of detections: {len(boxes)}")
        if len(boxes) > 0:
            for box in boxes:
                b = box.xyxy[0].cpu().numpy().tolist()
                conf = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())
                cls_name = model.names[cls_id]
                
                print(f"- Detected: {cls_name} (Confidence: {conf:.2f}) at BBOX: {b}")
        else:
            print("No instruments detected in this frame.")
    else:
        print("No results returned.")

if __name__ == "__main__":
    test_inference("models/yolov8s_cholec80.pt", "backend/uploads/340d20b9-8b10-40f5-bb76-b40fb7019274_clip_04.mp4")
