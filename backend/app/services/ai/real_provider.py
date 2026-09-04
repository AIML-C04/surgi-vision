import os
import cv2
from typing import Dict, Any, List
from ultralytics import YOLO
from app.services.ai.base import AIInferenceProvider

class RealInferenceProvider(AIInferenceProvider):
    def __init__(self):
        model_path = os.getenv("MODEL_PATH", "models/yolov8s_cholec80.pt")
        if not os.path.exists(model_path):
            # Try ascending one directory if running from backend/
            alt_path = os.path.join("..", model_path)
            if os.path.exists(alt_path):
                model_path = alt_path
            else:
                raise RuntimeError(f"Model checkpoint not found at {model_path} or {alt_path}. "
                                   f"Real inference requires the actual weights.")
        print(f"Loading Real YOLO Model from: {model_path}")
        self.model = YOLO(model_path)
        self.confidence_threshold = float(os.getenv("MODEL_CONFIDENCE_THRESHOLD", 0.5))

    def analyze_frame(self, frame_id: int, timestamp: float, frame=None) -> Dict[str, Any]:
        """
        Runs tracking/detection on the frame.
        We expect frame to be a numpy array (BGR image from cv2).
        """
        if frame is None:
            # Fallback if no frame provided (shouldn't happen in real run)
            return self._empty_result(frame_id, timestamp)

        # Run tracking using YOLO's built in tracker (BoT-SORT by default in Ultralytics, or ByteTrack)
        # persist=True keeps track histories across frames
        results = self.model.track(frame, persist=True, conf=self.confidence_threshold, verbose=False)
        
        detections = []
        
        if len(results) > 0:
            result = results[0]
            boxes = result.boxes
            
            if boxes is not None:
                for box in boxes:
                    # Get box coordinates as [x1, y1, x2, y2]
                    b = box.xyxy[0].cpu().numpy().tolist()
                    conf = float(box.conf[0].cpu().numpy())
                    cls_id = int(box.cls[0].cpu().numpy())
                    cls_name = self.model.names[cls_id]
                    
                    # Track ID might be None if the tracker hasn't assigned one yet
                    track_id = int(box.id[0].cpu().numpy()) if box.id is not None else None
                    
                    detections.append({
                        "class": cls_name,
                        "confidence": round(conf, 2),
                        "bbox": [round(x, 2) for x in b],
                        "track_id": track_id
                    })
                    
        return {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "detections": detections,
            "phase": {
                "name": "Not available",
                "confidence": 0.0
            }
        }
        
    def _empty_result(self, frame_id: int, timestamp: float) -> Dict[str, Any]:
        return {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "detections": [],
            "phase": {
                "name": "Not available",
                "confidence": 0.0
            }
        }

    def detect_instruments(self, frame) -> List[Dict[str, Any]]:
        pass
        
    def track_instruments(self, frame, previous_tracks) -> List[Dict[str, Any]]:
        pass
        
    def recognize_phase(self, frame_buffer) -> Dict[str, Any]:
        pass
