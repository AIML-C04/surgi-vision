from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.video import AnalysisSession, SurgicalPhase


@dataclass(frozen=True)
class PhasePrediction:
    phase_name: str
    start_time: float
    end_time: float
    confidence: float | None
    model_provider: str
    model_version: str
    taxonomy_version: str | None
    evidence: list[dict[str, Any]]


class PhaseRecognitionProvider(ABC):
    provider_name: str
    model_version: str | None
    taxonomy_version: str | None

    @property
    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def predict_phases(self, analysis: AnalysisSession) -> list[dict[str, Any]]:
        raise NotImplementedError


class UnavailablePhaseRecognitionProvider(PhaseRecognitionProvider):
    provider_name = "none"
    model_version = None
    taxonomy_version = None

    @property
    def available(self) -> bool:
        return False

    def predict_phases(self, analysis: AnalysisSession) -> list[dict[str, Any]]:
        return []


def get_phase_provider() -> PhaseRecognitionProvider:
    provider_name = (settings.PHASE_MODEL_PROVIDER or "none").strip().lower()
    if provider_name in {"", "none", "unavailable", "disabled"}:
        return UnavailablePhaseRecognitionProvider()
    raise RuntimeError(
        f"PHASE_MODEL_PROVIDER={provider_name} is configured, but no validated phase provider is registered"
    )


def _validate_prediction(
    prediction: dict[str, Any],
    analysis: AnalysisSession,
    provider: PhaseRecognitionProvider,
) -> PhasePrediction:
    phase_name = prediction.get("phase_name", prediction.get("phase"))
    start_time = prediction.get("start_time")
    end_time = prediction.get("end_time")
    confidence = prediction.get("confidence")
    model_version = prediction.get("model_version") or provider.model_version
    taxonomy_version = prediction.get("taxonomy_version") or provider.taxonomy_version
    if not isinstance(phase_name, str) or not phase_name.strip():
        raise ValueError("Phase prediction must include a phase name")
    if not isinstance(start_time, (int, float)) or not isinstance(end_time, (int, float)):
        raise ValueError("Phase prediction timestamps must be numeric")
    if start_time < 0 or end_time < start_time:
        raise ValueError("Phase prediction timestamps are invalid")
    if analysis.video.duration is not None and end_time > analysis.video.duration:
        raise ValueError("Phase prediction exceeds video duration")
    if confidence is not None and (not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
        raise ValueError("Phase prediction confidence must be between 0 and 1")
    if not isinstance(model_version, str) or not model_version.strip():
        raise ValueError("Phase prediction must include a model version")
    evidence = prediction.get("evidence") or []
    if not isinstance(evidence, list):
        raise ValueError("Phase prediction evidence must be a list")
    return PhasePrediction(
        phase_name=phase_name.strip(),
        start_time=float(start_time),
        end_time=float(end_time),
        confidence=float(confidence) if confidence is not None else None,
        model_provider=prediction.get("model_provider") or provider.provider_name,
        model_version=model_version,
        taxonomy_version=taxonomy_version,
        evidence=evidence,
    )


def merge_phase_predictions(predictions: list[PhasePrediction]) -> list[PhasePrediction]:
    merged: list[PhasePrediction] = []
    for prediction in sorted(predictions, key=lambda item: (item.start_time, item.end_time)):
        if merged and merged[-1].phase_name == prediction.phase_name and merged[-1].end_time == prediction.start_time:
            previous = merged[-1]
            confidence_values = [value for value in (previous.confidence, prediction.confidence) if value is not None]
            merged[-1] = PhasePrediction(
                phase_name=previous.phase_name,
                start_time=previous.start_time,
                end_time=prediction.end_time,
                confidence=sum(confidence_values) / len(confidence_values) if confidence_values else None,
                model_provider=previous.model_provider,
                model_version=previous.model_version,
                taxonomy_version=previous.taxonomy_version,
                evidence=previous.evidence + prediction.evidence,
            )
        else:
            merged.append(prediction)
    return merged


def recognize_and_persist_phases(
    db: Session,
    analysis: AnalysisSession,
    provider: PhaseRecognitionProvider | None = None,
) -> dict[str, Any]:
    db.query(SurgicalPhase).filter(SurgicalPhase.analysis_id == analysis.id).delete(synchronize_session=False)
    provider = provider or get_phase_provider()
    if not provider.available:
        db.flush()
        return {
            "status": "unavailable",
            "available": False,
            "provider": None,
            "model_version": None,
            "taxonomy_version": None,
            "reason": "No validated phase recognition model configured for this analysis.",
            "phases": [],
        }

    raw_predictions = provider.predict_phases(analysis)
    validated = [_validate_prediction(item, analysis, provider) for item in raw_predictions]
    phases = merge_phase_predictions(validated)
    for phase in phases:
        db.add(SurgicalPhase(
            analysis_id=analysis.id,
            name=phase.phase_name,
            start_time=phase.start_time,
            end_time=phase.end_time,
            confidence=phase.confidence,
            model_provider=phase.model_provider,
            model_version=phase.model_version,
            taxonomy_version=phase.taxonomy_version,
            evidence=phase.evidence,
        ))
    db.flush()
    return {
        "status": "completed",
        "available": True,
        "provider": provider.provider_name,
        "model_version": provider.model_version,
        "taxonomy_version": provider.taxonomy_version,
        "reason": None if phases else "No phase segments were produced by the configured model.",
        "phases": phases,
    }


def serialize_phase(phase: SurgicalPhase) -> dict[str, Any]:
    return {
        "id": str(phase.id),
        "analysis_id": str(phase.analysis_id),
        "phase_name": phase.name,
        "start_time": phase.start_time,
        "end_time": phase.end_time,
        "duration": phase.end_time - phase.start_time,
        "confidence": phase.confidence,
        "phase_model_provider": phase.model_provider,
        "phase_model_version": phase.model_version,
        "phase_taxonomy_version": phase.taxonomy_version,
        "evidence": phase.evidence or [],
        "evidence_count": len(phase.evidence or []),
        "created_at": phase.created_at,
    }
