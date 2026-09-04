# Research and Evaluation

SurgiVision evaluation runs operate on persisted outputs from a completed analysis. A run records the dataset version, analysis/model metadata, task, configuration, sample counts, metrics, and lifecycle timestamps. Historical runs are retained and can be exported as JSON or CSV.

## Ground truth

Detection accuracy is only calculated when the selected dataset contains real annotations matching the evaluated video. The accepted `json-manifest` annotation record contains `video_id`, `frame_id`, `class_name`, and `[x1, y1, x2, y2]` `bbox`; timestamp and track/event/phase fields may be added when those labels exist. Coordinates must be finite, non-negative, and have positive width and height. Dataset taxonomy classes are validated when supplied.

A dataset without annotations is valid for inference statistics, but precision, recall, F1, tracking scores, event scores, and phase scores remain unavailable. Unavailable is distinct from zero.

## Detection matching

The current detection evaluator uses a greedy highest-IoU match within the same video and frame, requires equal class names for a true positive, and uses an IoU threshold recorded in the run configuration. Unmatched predictions are false positives and unmatched annotations are false negatives. Wrong-class overlaps are represented in the confusion matrix and contribute one false positive and one false negative.

The evaluator reports overall and per-class TP, FP, FN, precision, recall, and F1. It does not claim mAP until an implementation with the required confidence ranking and IoU sweep is added.

## Other tasks

Tracking and event evaluation remain unavailable until suitable track-level or event-level ground truth is imported. Phase evaluation remains unavailable while `PHASE_MODEL_PROVIDER=none` or when phase annotations/model compatibility is absent. Model confidence is descriptive confidence from the provider and is not prediction correctness.

## Performance

Recorded analysis stores measured processing duration, processed frame count, skipped frame count, and effective FPS when available. These values describe this pipeline run and hardware; they are not accuracy measurements. Live inference separately reports measured latency and dropped frames in ephemeral live state.

## Reproducibility and comparison

Runs preserve model provider/version, dataset/version, taxonomy metadata, checkpoint identifier, IoU threshold, confidence configuration, and sampling source. The comparison endpoint only marks runs comparable when they reference the same dataset. Different datasets return an explicit not-directly-comparable result.

## Model integration

A future fine-tuned model implements the existing provider contract and returns normalized detections with class name, confidence, bounding box, frame sequence, timestamp, and optional track ID. Evaluation consumes the persisted normalized output, so replacing the checkpoint does not require frontend changes.
