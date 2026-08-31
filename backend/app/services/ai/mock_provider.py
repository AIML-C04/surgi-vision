import time
import random
from app.services.ai.base import AIInferenceProvider
from typing import Dict, Any, List

class MockInferenceProvider(AIInferenceProvider):
    def __init__(self):
        self.instruments = ["Grasper", "Scissors", "Clipper", "Forceps"]
        self.phases = ["Preparation", "Dissection", "Clipping", "Gallbladder Dissection", "Cleaning", "Closure"]

    def analyze_frame(self, frame_id: int, timestamp: float) -> Dict[str, Any]:
        """Returns mock analysis mimicking standard schema."""
        num_detections = random.randint(1, 3)
        detections = []
        for i in range(num_detections):
            detections.append({
                "class": random.choice(self.instruments),
                "confidence": round(random.uniform(0.75, 0.99), 2),
                "bbox": [
                    random.randint(50, 200),
                    random.randint(50, 200),
                    random.randint(250, 400),
                    random.randint(250, 400)
                ],
                "track_id": random.randint(1, 5)
            })
            
        return {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "detections": detections,
            "phase": {
                "name": self.phases[int(timestamp / 30) % len(self.phases)], # Change phase every 30 seconds
                "confidence": round(random.uniform(0.80, 0.99), 2)
            }
        }
        
    def detect_instruments(self, frame) -> List[Dict[str, Any]]:
        return []
        
    def track_instruments(self, frame, previous_tracks) -> List[Dict[str, Any]]:
        return []
        
    def recognize_phase(self, frame_buffer) -> Dict[str, Any]:
        return {}

class AnalysisTaskGenerator:
    """Simulates background video processing by emitting WebSocket messages."""
    pass
