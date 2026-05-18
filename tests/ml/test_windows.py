import numpy as np

from ml.windows import build_windows


def test_window_shape_and_stride():
    X = np.zeros((200, 10), dtype=np.float32)
    labels = ["normal"] * 200
    wins, wlabels = build_windows(X, labels, window_size=60, stride=4)
    assert wins.shape == ((200 - 60) // 4 + 1, 60, 10)
    assert len(wlabels) == wins.shape[0]


def test_majority_label_rule_assigns_type_when_geq_50pct():
    X = np.zeros((60, 10), dtype=np.float32)
    labels = ["cpu_spike"] * 31 + ["normal"] * 29
    wins, wlabels = build_windows(X, labels, window_size=60, stride=60)
    assert wlabels == ["cpu_spike"]


def test_majority_label_falls_back_to_normal_when_below_50pct():
    X = np.zeros((60, 10), dtype=np.float32)
    labels = ["cpu_spike"] * 25 + ["normal"] * 35
    wins, wlabels = build_windows(X, labels, window_size=60, stride=60)
    assert wlabels == ["normal"]


def test_mixed_anomaly_types_collapse_to_normal():
    X = np.zeros((60, 10), dtype=np.float32)
    labels = ["cpu_spike"] * 20 + ["memory_leak"] * 20 + ["normal"] * 20
    wins, wlabels = build_windows(X, labels, window_size=60, stride=60)
    assert wlabels == ["normal"]
