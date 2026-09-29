import numpy as np

from ml.models.cnn_lstm_classifier import build_cnn_lstm_classifier


def test_classifier_io_shape():
    m = build_cnn_lstm_classifier(window_size=60, n_features=10, n_classes=7)
    p = m.predict(np.zeros((3, 60, 10), dtype=np.float32), verbose=0)
    assert p.shape == (3, 7)
    assert np.allclose(p.sum(axis=1), 1.0, atol=1e-4)
