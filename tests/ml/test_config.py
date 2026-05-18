from ml.config import (
    CLASSES,
    FEATURE_COLS,
    STRIDE,
    WINDOW_SIZE,
    index_to_label,
    label_to_index,
)


def test_classes_canonical_order():
    assert CLASSES == [
        "normal",
        "cpu_spike",
        "memory_leak",
        "disk_fill",
        "network_storm",
        "container_crash",
        "service_down",
    ]


def test_feature_cols_length():
    assert len(FEATURE_COLS) == 10
    assert "cpu_percent" in FEATURE_COLS
    assert "containers_running_ratio" in FEATURE_COLS


def test_window_constants():
    assert WINDOW_SIZE == 60
    assert STRIDE == 4


def test_label_round_trip():
    for i, c in enumerate(CLASSES):
        assert label_to_index(c) == i
        assert index_to_label(i) == c
