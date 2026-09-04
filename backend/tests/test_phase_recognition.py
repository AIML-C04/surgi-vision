from types import SimpleNamespace

import pytest

from app.services.phase_recognition import (
    PhasePrediction,
    UnavailablePhaseRecognitionProvider,
    _validate_prediction,
    merge_phase_predictions,
)


def test_unavailable_provider_returns_no_predictions():
    provider = UnavailablePhaseRecognitionProvider()
    assert provider.available is False
    assert provider.predict_phases(SimpleNamespace()) == []


def test_adjacent_same_phase_windows_merge_without_filling_gaps():
    first = PhasePrediction("validated", 0.0, 1.0, 0.8, "test", "1", "taxonomy", [])
    second = PhasePrediction("validated", 1.0, 2.0, 0.6, "test", "1", "taxonomy", [])
    gap = PhasePrediction("validated", 3.0, 4.0, 0.9, "test", "1", "taxonomy", [])
    result = merge_phase_predictions([gap, second, first])
    assert [(item.start_time, item.end_time) for item in result] == [(0.0, 2.0), (3.0, 4.0)]
    assert result[0].confidence == pytest.approx(0.7)


def test_prediction_validation_rejects_invalid_confidence_and_duration():
    analysis = SimpleNamespace(video=SimpleNamespace(duration=10.0))
    provider = SimpleNamespace(provider_name="test", model_version="1", taxonomy_version=None)
    with pytest.raises(ValueError, match="confidence"):
        _validate_prediction({"phase": "validated", "start_time": 1, "end_time": 2, "confidence": 2}, analysis, provider)
    with pytest.raises(ValueError, match="duration"):
        _validate_prediction({"phase": "validated", "start_time": 1, "end_time": 11, "confidence": 0.5}, analysis, provider)
