import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationDataset, EvaluationRun
from app.models.video import AnalysisSession, Detection


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def validate_annotations(annotations: list[dict[str, Any]], taxonomy_classes: list[str] | None = None) -> None:
    allowed = set(taxonomy_classes or [])
    for index, annotation in enumerate(annotations):
        required = ("video_id", "frame_id", "class_name", "bbox")
        if any(field not in annotation for field in required):
            raise ValueError(f"Annotation {index} is missing a required field")
        if not isinstance(annotation["video_id"], str) or not annotation["video_id"]:
            raise ValueError(f"Annotation {index} has an invalid video_id")
        if not isinstance(annotation["frame_id"], int) or annotation["frame_id"] < 0:
            raise ValueError(f"Annotation {index} has an invalid frame_id")
        if not isinstance(annotation["class_name"], str) or not annotation["class_name"].strip():
            raise ValueError(f"Annotation {index} has an invalid class_name")
        if allowed and annotation["class_name"] not in allowed:
            raise ValueError(f"Annotation {index} uses a class outside the dataset taxonomy")
        bbox = annotation["bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4 or not all(_finite_number(value) for value in bbox):
            raise ValueError(f"Annotation {index} has an invalid bbox")
        x1, y1, x2, y2 = bbox
        if x1 < 0 or y1 < 0 or x2 <= x1 or y2 <= y1:
            raise ValueError(f"Annotation {index} has invalid bbox coordinates")
        if "timestamp" in annotation and (not _finite_number(annotation["timestamp"]) or annotation["timestamp"] < 0):
            raise ValueError(f"Annotation {index} has an invalid timestamp")


def _iou(left: list[float], right: list[float]) -> float:
    x1 = max(left[0], right[0])
    y1 = max(left[1], right[1])
    x2 = min(left[2], right[2])
    y2 = min(left[3], right[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _scores(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def detection_metrics(predictions: list[dict[str, Any]], annotations: list[dict[str, Any]], iou_threshold: float = 0.5) -> dict[str, Any]:
    grouped_predictions: defaultdict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    grouped_truth: defaultdict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for prediction in predictions:
        grouped_predictions[(prediction["video_id"], prediction["frame_id"])].append(prediction)
    for annotation in annotations:
        grouped_truth[(annotation["video_id"], annotation["frame_id"])].append(annotation)

    counts = Counter()
    confusion: Counter[tuple[str, str]] = Counter()
    for key in set(grouped_predictions) | set(grouped_truth):
        matched_truth: set[int] = set()
        for prediction in sorted(grouped_predictions[key], key=lambda item: item.get("confidence", 0), reverse=True):
            candidates = [(index, _iou(prediction["bbox"], truth["bbox"])) for index, truth in enumerate(grouped_truth[key]) if index not in matched_truth]
            if candidates:
                truth_index, overlap = max(candidates, key=lambda item: item[1])
                if overlap >= iou_threshold:
                    matched_truth.add(truth_index)
                    truth_class = grouped_truth[key][truth_index]["class_name"]
                    if truth_class == prediction["class_name"]:
                        counts[prediction["class_name"], "tp"] += 1
                    else:
                        counts[prediction["class_name"], "fp"] += 1
                        counts[truth_class, "fn"] += 1
                        confusion[truth_class, prediction["class_name"]] += 1
                    continue
            counts[prediction["class_name"], "fp"] += 1
        for index, truth in enumerate(grouped_truth[key]):
            if index not in matched_truth:
                counts[truth["class_name"], "fn"] += 1

    classes = sorted({item["class_name"] for item in predictions + annotations})
    per_class = {}
    for class_name in classes:
        per_class[class_name] = _scores(counts[class_name, "tp"], counts[class_name, "fp"], counts[class_name, "fn"])
    overall = _scores(sum(item["tp"] for item in per_class.values()), sum(item["fp"] for item in per_class.values()), sum(item["fn"] for item in per_class.values()))
    return {"overall": overall, "per_class": per_class, "confusion_matrix": {class_name: {other: confusion[class_name, other] for other in classes} for class_name in classes}, "iou_threshold": iou_threshold, "matching_strategy": "greedy highest-IoU match by video, frame, and class"}


def _serialize_detection(detection: Detection) -> dict[str, Any]:
    return {"video_id": str(detection.analysis.video_id), "frame_id": detection.frame_id, "timestamp": detection.timestamp, "class_name": detection.class_name, "confidence": detection.confidence, "bbox": detection.bbox, "track_id": detection.track_id}


def build_evaluation_run(db: Session, dataset: EvaluationDataset, analysis: AnalysisSession, configuration: dict[str, Any]) -> EvaluationRun:
    run = EvaluationRun(dataset_id=dataset.id, user_id=dataset.user_id, analysis_id=analysis.id, model_provider=analysis.model_provider, model_name=configuration.get("model_name"), model_version=analysis.model_version, checkpoint_identifier=configuration.get("checkpoint_identifier"), task="detection", configuration=configuration, status="running", started_at=datetime.now(timezone.utc))
    db.add(run)
    db.flush()
    detections = db.query(Detection).filter(Detection.analysis_id == analysis.id).order_by(Detection.frame_id).all()
    predictions = [_serialize_detection(detection) for detection in detections]
    annotations = [item for item in (dataset.annotations or []) if item.get("video_id") == str(analysis.video_id)]
    classes = sorted({item["class_name"] for item in predictions})
    confidences = [item["confidence"] for item in predictions]
    run.sample_counts = {"predictions": len(predictions), "predicted_frames": len({item["frame_id"] for item in predictions}), "ground_truth_annotations": len(annotations), "ground_truth_available": bool(annotations)}
    metrics = {"model_confidence": {"mean": sum(confidences) / len(confidences) if confidences else None, "minimum": min(confidences) if confidences else None, "maximum": max(confidences) if confidences else None}, "prediction_counts_by_class": dict(Counter(item["class_name"] for item in predictions)), "performance": {"processing_duration_seconds": analysis.processing_duration, "processed_frames": analysis.processed_frames, "skipped_frames": analysis.skipped_frames, "effective_fps": analysis.processed_frames / analysis.processing_duration if analysis.processing_duration and analysis.processed_frames else None}}
    taxonomy_version = configuration.get("taxonomy_version")
    taxonomy_compatible = not taxonomy_version or not dataset.taxonomy_version or taxonomy_version == dataset.taxonomy_version
    if annotations and taxonomy_compatible:
        metrics["detection"] = detection_metrics(predictions, annotations, float(configuration.get("iou_threshold", 0.5)))
    elif annotations and not taxonomy_compatible:
        metrics["detection"] = {"status": "unavailable", "reason": "Evaluation unavailable - model and dataset taxonomies are incompatible.", "dataset_taxonomy_version": dataset.taxonomy_version, "model_taxonomy_version": taxonomy_version}
    else:
        metrics["detection"] = {"status": "unavailable", "reason": "Accuracy unavailable - ground-truth annotations are not available."}
    metrics["tracking"] = {"status": "unavailable", "reason": "Tracking evaluation unavailable - track-level ground truth is not available."}
    metrics["events"] = {"status": "unavailable", "reason": "Event evaluation unavailable - event ground truth is not available."}
    metrics["phases"] = {"status": "unavailable", "reason": "Phase evaluation unavailable."}
    run.metrics = metrics
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    return run
