from __future__ import annotations

CLASSES: list[str] = [
    "normal",
    "cpu_spike",
    "memory_leak",
    "disk_fill",
    "network_storm",
    "container_crash",
    "service_down",
]

FEATURE_COLS: list[str] = [
    "cpu_percent",
    "load_avg_1m",
    "mem_percent",
    "swap_used_mb",
    "disk_percent",
    "disk_read_bps",
    "disk_write_bps",
    "net_in_bps",
    "net_out_bps",
    "containers_running_ratio",
]

WINDOW_SIZE: int = 60
STRIDE: int = 4
INFER_STRIDE: int = 4

_LABEL_TO_IDX = {c: i for i, c in enumerate(CLASSES)}

def label_to_index(label: str) -> int:
    return _LABEL_TO_IDX[label]

def index_to_label(idx: int) -> str:
    return CLASSES[idx]
