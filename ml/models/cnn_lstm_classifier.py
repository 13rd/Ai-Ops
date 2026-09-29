from __future__ import annotations

from tensorflow import keras
from tensorflow.keras import layers

def build_cnn_lstm_classifier(
    window_size: int = 60, n_features: int = 10, n_classes: int = 7,
) -> keras.Model:
    inputs = keras.Input(shape=(window_size, n_features))
    x = layers.Conv1D(32, 5, padding="same", activation="relu")(inputs)
    x = layers.MaxPool1D(2)(x)
    x = layers.Conv1D(64, 3, padding="same", activation="relu")(x)
    x = layers.MaxPool1D(2)(x)
    x = layers.LSTM(32)(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(32, activation="relu")(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(n_classes, activation="softmax")(x)
    model = keras.Model(inputs, outputs, name="cnn_lstm_classifier")
    model.compile(
        optimizer=keras.optimizers.Adam(1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model
