import json
from pathlib import Path

import numpy as np
import pytest

from ml.models.cnn_lstm_classifier import build_cnn_lstm_classifier
from ml.models.lstm_autoencoder import build_lstm_autoencoder
from ml.registry import ModelRegistry


@pytest.fixture
def tiny_models_dir(tmp_path: Path) -> Path:
    ae = build_lstm_autoencoder()
    clf = build_cnn_lstm_classifier()
    ae.save(tmp_path / "lstm_ae.keras")
    clf.save(tmp_path / "classifier.keras")
    (tmp_path / "threshold.json").write_text(
        json.dumps({"threshold": 1.0, "mean": 0.5, "std": 0.2})
    )
    np.save(tmp_path / "background.npy",
            np.zeros((10, 60, 10), dtype=np.float32))
    return tmp_path


def test_registry_reports_missing_models(tmp_path):
    r = ModelRegistry(models_dir=tmp_path)
    r.load()
    assert not r.has_models()


def test_registry_loads_when_artifacts_present(tiny_models_dir):
    r = ModelRegistry(models_dir=tiny_models_dir)
    r.load()
    assert r.has_models()
    assert r.threshold == 1.0
    x = np.zeros((1, 60, 10), dtype=np.float32)
    assert r.ae.predict(x, verbose=0).shape == (1, 60, 10)
    assert r.classifier.predict(x, verbose=0).shape == (1, 7)
