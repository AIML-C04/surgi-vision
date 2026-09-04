import csv
import io
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.evaluation import EvaluationDataset, EvaluationRun
from app.models.user import User
from app.models.video import AnalysisSession, Video
from app.services.evaluation import build_evaluation_run, validate_annotations

router = APIRouter()


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    annotation_format: str = "json-manifest"
    taxonomy_version: str | None = None
    taxonomy_classes: list[str] = Field(default_factory=list)
    annotations: list[dict[str, Any]] = Field(default_factory=list, max_length=100000)


class RunCreate(BaseModel):
    dataset_id: UUID
    video_id: UUID
    model_name: str | None = None
    checkpoint_identifier: str | None = None
    taxonomy_version: str | None = None
    iou_threshold: float = Field(default=0.5, ge=0, le=1)


def _dataset_or_404(db: Session, dataset_id: UUID, user: User) -> EvaluationDataset:
    dataset = db.query(EvaluationDataset).filter(EvaluationDataset.id == dataset_id, EvaluationDataset.user_id == user.id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Evaluation dataset not found")
    return dataset


def _serialize_run(run: EvaluationRun) -> dict[str, Any]:
    return {"id": str(run.id), "dataset_id": str(run.dataset_id), "analysis_id": str(run.analysis_id) if run.analysis_id else None, "model_provider": run.model_provider, "model_name": run.model_name, "model_version": run.model_version, "checkpoint_identifier": run.checkpoint_identifier, "task": run.task, "configuration": run.configuration, "status": run.status, "sample_counts": run.sample_counts, "metrics": run.metrics, "errors": run.errors, "started_at": run.started_at, "completed_at": run.completed_at, "created_at": run.created_at}


@router.post("/datasets")
def create_dataset(payload: DatasetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        validate_annotations(payload.annotations, payload.taxonomy_classes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    dataset = EvaluationDataset(user_id=current_user.id, name=payload.name, version=payload.version, annotation_format=payload.annotation_format, taxonomy_version=payload.taxonomy_version, taxonomy_classes=payload.taxonomy_classes, ground_truth_available=bool(payload.annotations), annotations=payload.annotations or None)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return {"id": str(dataset.id), "name": dataset.name, "version": dataset.version, "annotation_format": dataset.annotation_format, "taxonomy_version": dataset.taxonomy_version, "ground_truth_available": dataset.ground_truth_available, "annotation_count": len(payload.annotations)}


@router.get("/datasets")
def list_datasets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    datasets = db.query(EvaluationDataset).filter(EvaluationDataset.user_id == current_user.id).order_by(EvaluationDataset.created_at.desc()).all()
    return [{"id": str(dataset.id), "name": dataset.name, "version": dataset.version, "annotation_format": dataset.annotation_format, "taxonomy_version": dataset.taxonomy_version, "ground_truth_available": dataset.ground_truth_available, "annotation_count": len(dataset.annotations or [])} for dataset in datasets]


@router.post("/runs")
def create_evaluation_run(payload: RunCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    dataset = _dataset_or_404(db, payload.dataset_id, current_user)
    video = db.query(Video).filter(Video.id == payload.video_id, Video.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    analysis = db.query(AnalysisSession).filter(AnalysisSession.video_id == video.id, AnalysisSession.status == "completed").order_by(AnalysisSession.created_at.desc()).first()
    if not analysis:
        raise HTTPException(status_code=409, detail="A completed analysis is required before evaluation")
    configuration = {"iou_threshold": payload.iou_threshold, "confidence_threshold": None, "frame_sampling": "persisted analysis output"}
    if payload.model_name:
        configuration["model_name"] = payload.model_name
    if payload.checkpoint_identifier:
        configuration["checkpoint_identifier"] = payload.checkpoint_identifier
    if payload.taxonomy_version:
        configuration["taxonomy_version"] = payload.taxonomy_version
    run = build_evaluation_run(db, dataset, analysis, configuration)
    db.commit()
    db.refresh(run)
    return _serialize_run(run)


@router.get("/runs")
def list_runs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    runs = db.query(EvaluationRun).filter(EvaluationRun.user_id == current_user.id).order_by(EvaluationRun.created_at.desc()).all()
    return [_serialize_run(run) for run in runs]


@router.get("/runs/{run_id}")
def get_run(run_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = db.query(EvaluationRun).filter(EvaluationRun.id == run_id, EvaluationRun.user_id == current_user.id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    return _serialize_run(run)


@router.get("/compare")
def compare_runs(run_a_id: UUID, run_b_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    runs = db.query(EvaluationRun).filter(EvaluationRun.id.in_([run_a_id, run_b_id]), EvaluationRun.user_id == current_user.id).all()
    by_id = {run.id: run for run in runs}
    if run_a_id not in by_id or run_b_id not in by_id:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    run_a, run_b = by_id[run_a_id], by_id[run_b_id]
    if run_a.dataset_id != run_b.dataset_id:
        return {"comparable": False, "reason": "Comparison not directly comparable - evaluation datasets differ.", "run_a": _serialize_run(run_a), "run_b": _serialize_run(run_b)}
    return {"comparable": True, "reason": None, "dataset_id": str(run_a.dataset_id), "run_a": _serialize_run(run_a), "run_b": _serialize_run(run_b)}


@router.get("/runs/{run_id}/export")
def export_run(run_id: UUID, format: str = "json", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = db.query(EvaluationRun).filter(EvaluationRun.id == run_id, EvaluationRun.user_id == current_user.id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")
    payload = _serialize_run(run)
    if format.lower() == "json":
        import json
        return PlainTextResponse(json.dumps(payload, default=str, indent=2), media_type="application/json", headers={"Content-Disposition": f"attachment; filename=evaluation-{run.id}.json"})
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Format must be json or csv")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["run_id", "dataset_id", "analysis_id", "model_provider", "model_version", "status", "metric", "value"])
    for section, values in (run.metrics or {}).items():
        if isinstance(values, dict):
            for key, value in values.items():
                writer.writerow([run.id, run.dataset_id, run.analysis_id, run.model_provider, run.model_version, run.status, f"{section}.{key}", value if not isinstance(value, (dict, list)) else str(value)])
    return PlainTextResponse(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=evaluation-{run.id}.csv"})


@router.get("/overview")
def get_research_overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    analyses = db.query(AnalysisSession).join(Video).filter(Video.user_id == current_user.id, AnalysisSession.status == "completed").order_by(AnalysisSession.created_at.desc()).all()
    return {"model": {"provider": analyses[0].model_provider if analyses else None, "version": analyses[0].model_version if analyses else None}, "analyses": [{"analysis_id": str(analysis.id), "video_id": str(analysis.video_id), "model_provider": analysis.model_provider, "model_version": analysis.model_version, "processing_duration_seconds": analysis.processing_duration, "processed_frames": analysis.processed_frames, "skipped_frames": analysis.skipped_frames, "detection_count": len(analysis.detections), "ground_truth_available": False} for analysis in analyses], "limitations": ["Quantitative model accuracy evaluation is not currently available because ground-truth annotations are not present.", "Tracking evaluation unavailable - track-level ground truth is not available.", "Event evaluation unavailable - event ground truth is not available.", "Phase evaluation unavailable."]}
