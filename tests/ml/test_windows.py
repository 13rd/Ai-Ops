import numpy as np

from ml.windows import build_windows


def test_window_shape_and_stride():
    X = np.zeros((200, 10), dtype=np.float32)
    labels = ["normal"] * 200
    wins, wlabels = build_windows(X, labels, window_size=60, stride=4)
    assert wins.shape == ((200 - 60) // 4 + 1, 60, 10)
    assert len(wlabels) == wins.shape[0]
    assert set(wlabels) == {"normal"}


def test_anomaly_at_tail_labels_window():
    # 15 contiguous anomaly samples at the window end (>= min_tail) -> labelled
    X = np.zeros((60, 10), dtype=np.float32)
    labels = ["normal"] * 45 + ["cpu_spike"] * 15
    _, wlabels = build_windows(X, labels, window_size=60, stride=60, min_tail=10)
    assert wlabels == ["cpu_spike"]


def test_short_tail_run_stays_normal():
    # only 5 trailing anomaly samples (< min_tail) -> normal
    X = np.zeros((60, 10), dtype=np.float32)
    labels = ["normal"] * 55 + ["cpu_spike"] * 5
    _, wlabels = build_windows(X, labels, window_size=60, stride=60, min_tail=10)
    assert wlabels == ["normal"]


def test_anomaly_in_middle_with_recovered_tail_is_normal():
    # anomaly already ended; tail recovered to normal -> normal (online rule)
    X = np.zeros((60, 10), dtype=np.float32)
    labels = ["normal"] * 10 + ["cpu_spike"] * 30 + ["normal"] * 20
    _, wlabels = build_windows(X, labels, window_size=60, stride=60, min_tail=10)
    assert wlabels == ["normal"]


def test_only_trailing_type_counts():
    # earlier memory_leak does not extend the trailing run of cpu_spike
    X = np.zeros((60, 10), dtype=np.float32)
    labels = ["memory_leak"] * 40 + ["cpu_spike"] * 20
    _, wlabels = build_windows(X, labels, window_size=60, stride=60, min_tail=10)
    assert wlabels == ["cpu_spike"]
