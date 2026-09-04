import pytest

from app.services.evaluation import detection_metrics, validate_annotations


def test_detection_metrics_counts_tp_fp_fn_and_iou_match():
    predictions = [
        {"video_id": "v", "frame_id": 1, "class_name": "Grasper", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
        {"video_id": "v", "frame_id": 1, "class_name": "Hook", "confidence": 0.8, "bbox": [20, 20, 30, 30]},
    ]
    annotations = [
        {"video_id": "v", "frame_id": 1, "class_name": "Grasper", "bbox": [0, 0, 10, 10]},
        {"video_id": "v", "frame_id": 1, "class_name": "Clipper", "bbox": [40, 40, 50, 50]},
    ]
    result = detection_metrics(predictions, annotations, 0.5)
    assert result["overall"] == {"tp": 1, "fp": 1, "fn": 1, "precision": 0.5, "recall": 0.5, "f1": 0.5}
    assert result["per_class"]["Grasper"]["tp"] == 1
    assert result["per_class"]["Hook"]["fp"] == 1
    assert result["per_class"]["Clipper"]["fn"] == 1


def test_annotation_validation_rejects_bad_bbox_and_unknown_taxonomy_class():
    with pytest.raises(ValueError, match="bbox"):
        validate_annotations([{"video_id": "v", "frame_id": 1, "class_name": "Grasper", "bbox": [0, 0, 0, 1]}])
    with pytest.raises(ValueError, match="taxonomy"):
        validate_annotations([{"video_id": "v", "frame_id": 1, "class_name": "Hook", "bbox": [0, 0, 1, 1]}], ["Grasper"])
