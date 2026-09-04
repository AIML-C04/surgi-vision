from abc import ABC, abstractmethod
from typing import Dict, Any, List

class AIInferenceProvider(ABC):
    @abstractmethod
    def analyze_frame(self, frame) -> Dict[str, Any]:
        """Analyzes a single frame and returns detections."""
        pass
        
    @abstractmethod
    def detect_instruments(self, frame) -> List[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def track_instruments(self, frame, previous_tracks) -> List[Dict[str, Any]]:
        pass
        