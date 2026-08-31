# AI Model Integration Guide

SurgiVision AI is built with a decoupled architecture. The frontend, backend, database, and analytics layers do not depend directly on a specific AI model.

The current implementation utilizes a `RealInferenceProvider` connected to a local YOLO model, but it can be toggled to a `MockInferenceProvider` for demonstrations.

## 1. Where to put the `.pt` file

Place your YOLO model checkpoint (e.g., `yolov8s_cholec80.pt`) in the `models/` directory at the root of the project.

```text
SurgiVision-AI/
└── models/
    └── yolov8s_cholec80.pt
```

## 2. Required Python Packages

To run the real model, ensure the following are installed in your backend virtual environment (they are included in `backend/requirements.txt`):
- `ultralytics`
- `opencv-python-headless` (or `opencv-python`)
- `torch`

## 3. Environment Variables

Configure the `backend/.env` file to point to your model and activate it:

```env
# Switch between 'local' and 'mock'
MODEL_PROVIDER=local

# Path to the model
MODEL_PATH=models/yolov8s_cholec80.pt

# Minimum confidence threshold (0.0 to 1.0)
MODEL_CONFIDENCE_THRESHOLD=0.5

# Downsampling frame rate for real-time capability (Process every N frames)
PROCESS_EVERY_N_FRAMES=5
```

## 4. How the `RealInferenceProvider` Works

The core abstraction is defined in `backend/app/services/ai/base.py`:

```python
class AIInferenceProvider(ABC):
    @abstractmethod
    def analyze_frame(self, frame_id, timestamp, frame) -> Dict[str, Any]:
        pass
```

The `RealInferenceProvider` (located in `backend/app/services/ai/real_provider.py`) does the following:
1. Loads the YOLO model via `ultralytics.YOLO` exactly once upon server startup to save memory and reduce latency.
2. The `processor.py` extracts frames from the uploaded video file using OpenCV (`cv2.VideoCapture`).
3. Each extracted frame is passed to `analyze_frame()`.
4. The provider runs `model.track(frame, persist=True)` to handle both **Detection** and **Tracking**.
5. It formats the outputs (bounding boxes, confidences, class names, track IDs) into the standardized application schema.

## 5. Expected Model Output Schema

Regardless of the underlying model, the provider must return a dictionary matching this schema. The frontend consumes this format over WebSockets:

```json
{
  "frame_id": 125,
  "timestamp": 4.16,
  "detections": [
    {
      "class": "grasper",
      "confidence": 0.94,
      "bbox": [120, 80, 340, 290],
      "track_id": 1
    }
  ],
  "phase": {
    "name": "Not available",
    "confidence": 0.0
  }
}
```

## 6. Tracking Architecture

We utilize Ultralytics' built-in tracking module (which typically runs BoT-SORT or ByteTrack under the hood). By passing `persist=True` during inference, the tracker assigns stable `track_id` integers to instruments across frames. These IDs are piped directly to the frontend timeline and UI without any additional custom logic.

## 7. Current Phase-Recognition Limitation

**Important:** The integrated YOLO model (`yolov8s_cholec80.pt`) is purely an **Object Detection** model. It does not perform surgical phase classification on its own. 

To maintain research integrity, the `RealInferenceProvider` explicitly hardcodes the phase response to:
```json
{
  "name": "Not available",
  "confidence": 0.0
}
```
The frontend gracefully detects this and displays "Phase model not yet connected."

## 8. How to Switch Between Mock and Local Mode

If you are developing UI features on a machine without the model file or without sufficient computational power, simply change your `.env`:

```env
MODEL_PROVIDER=mock
```

This will bypass the `RealInferenceProvider` and load the `MockInferenceProvider`, streaming simulated random bounding boxes and fake phase transitions to the frontend.

## 9. How to Replace the Model Later

To upgrade the model in the future:
1. Drop the new `.pt` file into the `models/` directory.
2. Update the `MODEL_PATH` in your `.env`.
3. Restart the FastAPI backend.

Because of the decoupled `AIInferenceProvider` architecture, no modifications to the database schema or the React frontend are required.
