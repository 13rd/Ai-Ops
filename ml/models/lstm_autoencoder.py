"""LSTM Autoencoder for anomaly detection via reconstruction error."""
from __future__ import annotations

from tensorflow import keras
from tensorflow.keras import layers


def build_lstm_autoencoder(window_size: int = 60, n_features: int = 10) -> keras.Model:
    inputs = keras.Input(shape=(window_size, n_features))
    x = layers.LSTM(32, return_sequences=True)(inputs)
    x = layers.LSTM(16, return_sequences=False)(x)
    x = layers.RepeatVector(window_size)(x)
    x = layers.LSTM(16, return_sequences=True)(x)
    x = layers.LSTM(32, return_sequences=True)(x)
    outputs = layers.TimeDistributed(layers.Dense(n_features))(x)
    model = keras.Model(inputs, outputs, name="lstm_autoencoder")
    model.compile(optimizer=keras.optimizers.Adam(1e-3), loss="mse")
    return model
