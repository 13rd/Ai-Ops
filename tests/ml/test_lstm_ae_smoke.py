import numpy as np

from ml.models.lstm_autoencoder import build_lstm_autoencoder


def test_lstm_ae_io_shape():
    model = build_lstm_autoencoder(window_size=60, n_features=10)
    X = np.zeros((2, 60, 10), dtype=np.float32)
    Y = model.predict(X, verbose=0)
    assert Y.shape == (2, 60, 10)


def test_lstm_ae_overfits_one_sample():
    model = build_lstm_autoencoder(window_size=10, n_features=3)
    X = np.random.RandomState(0).rand(1, 10, 3).astype(np.float32)
    h = model.fit(X, X, epochs=120, verbose=0)
    initial = h.history["loss"][0]
    final = h.history["loss"][-1]
    assert final < initial * 0.5, f"loss did not improve: {initial} -> {final}"
