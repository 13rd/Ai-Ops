from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timedelta
from pathlib import Path

CLASSES_ANOM = [
    "cpu_spike", "memory_leak", "disk_fill",
    "network_storm", "container_crash", "service_down",
]

BYTE_COUNTER_FIELDS = (
    "disk_read_bytes", "disk_write_bytes", "network_in_bytes", "network_out_bytes",
)

def accumulate_counters(sample: dict, acc: dict) -> None:

    for f in BYTE_COUNTER_FIELDS:
        acc[f] = acc.get(f, 0) + int(sample[f])
        sample[f] = acc[f]

def _normal_sample(rng: random.Random, hour: float, disk_used_gb: float) -> dict:
    daily = 5 * math.sin(2 * math.pi * hour / 24)
    cpu = max(8.0, min(60.0, rng.gauss(30.0 + daily, 4.5)))
    mem_pct = max(25.0, min(55.0, rng.gauss(38.0, 2.5)))
    disk_pct = max(20.0, min(60.0, disk_used_gb / 500 * 100))
    net_in = max(5_000, rng.gauss(220_000, 45_000))
    net_out = max(5_000, rng.gauss(120_000, 25_000))
    disk_read = max(0, rng.gauss(180_000, 60_000))
    disk_write = max(0, rng.gauss(140_000, 50_000))
    return dict(
        cpu_usage_percent=round(cpu, 2),
        memory_usage_percent=round(mem_pct, 2),
        memory_used_mb=round(32_768 * mem_pct / 100, 1),
        memory_free_mb=round(32_768 * (1 - mem_pct / 100), 1),
        memory_cached_mb=round(rng.gauss(4500, 250), 1),
        swap_used_mb=round(max(0.0, rng.gauss(40, 20)), 1),
        disk_usage_percent=round(disk_pct, 2),
        disk_used_gb=round(disk_used_gb, 2),
        disk_free_gb=round(500 - disk_used_gb, 2),
        network_in_bytes=int(net_in),
        network_out_bytes=int(net_out),
        disk_read_bytes=int(disk_read),
        disk_write_bytes=int(disk_write),
        load_average_1m=round(cpu / 100 * 8 * 0.85 + rng.gauss(0, 0.1), 2),
        load_average_5m=round(cpu / 100 * 8 * 0.7 + rng.gauss(0, 0.1), 2),
        load_average_15m=round(cpu / 100 * 8 * 0.6 + rng.gauss(0, 0.1), 2),
        uptime_seconds=0,
        process_count=int(80 + cpu * 0.6 + rng.gauss(0, 4)),
        active_connections=int(15 + cpu * 0.3 + rng.gauss(0, 4)),
        temperature_celsius=round(42 + cpu * 0.2 + rng.gauss(0, 0.8), 1),
        container_count=4,
        containers=[{"name": n, "status": "running"} for n in
                    ("sim-web", "sim-database", "sim-worker", "sim-cache")],
        services_summary={},
    )

def _apply_anomaly(sample: dict, atype: str, rng: random.Random, progress: float):

    if atype == "cpu_spike":
        sample["cpu_usage_percent"] = round(rng.uniform(85.0, 99.0), 2)
        sample["load_average_1m"] = round(rng.uniform(8.5, 16.0), 2)
        sample["load_average_5m"] = round(rng.uniform(7.0, 13.0), 2)
        sample["process_count"] = int(sample["process_count"] + rng.randint(30, 80))
        sample["temperature_celsius"] = round(rng.uniform(65, 82), 1)
    elif atype == "memory_leak":
        target_pct = 55.0 + 38.0 * progress
        target_pct += rng.gauss(0, 1.5)
        target_pct = max(50.0, min(96.0, target_pct))
        sample["memory_usage_percent"] = round(target_pct, 2)
        sample["memory_used_mb"] = round(32_768 * target_pct / 100, 1)
        sample["memory_free_mb"] = round(32_768 * (1 - target_pct / 100), 1)
        sample["swap_used_mb"] = round(rng.uniform(800, 2400) * progress, 1)
    elif atype == "disk_fill":
        target_pct = 65.0 + 30.0 * progress
        target_pct += rng.gauss(0, 1.0)
        target_pct = max(60.0, min(97.0, target_pct))
        sample["disk_usage_percent"] = round(target_pct, 2)
        sample["disk_used_gb"] = round(500 * target_pct / 100, 2)
        sample["disk_free_gb"] = round(500 * (1 - target_pct / 100), 2)
        sample["disk_write_bytes"] = int(rng.uniform(1_800_000, 3_500_000))
    elif atype == "network_storm":
        sample["network_in_bytes"] = int(rng.uniform(2_000_000, 8_000_000))
        sample["network_out_bytes"] = int(rng.uniform(1_500_000, 6_000_000))
        sample["active_connections"] = int(rng.uniform(200, 600))
    elif atype == "container_crash":
        crashed_idx = rng.randint(0, 3)
        for i, c in enumerate(sample["containers"]):
            c["status"] = "crashed" if i == crashed_idx else "running"
        sample["container_count"] = 4
        sample["cpu_usage_percent"] = round(sample["cpu_usage_percent"] * 0.7, 2)
    elif atype == "service_down":
        for i, c in enumerate(sample["containers"]):
            c["status"] = "stopped" if i in (0, 1) else "running"
        sample["cpu_usage_percent"] = round(rng.uniform(3.0, 12.0), 2)
        sample["load_average_1m"] = round(rng.uniform(0.05, 0.4), 2)
        sample["load_average_5m"] = round(rng.uniform(0.1, 0.5), 2)
        sample["network_in_bytes"] = int(rng.uniform(2_000, 25_000))
        sample["network_out_bytes"] = int(rng.uniform(1_000, 15_000))
        sample["active_connections"] = int(rng.uniform(0, 8))

def generate_server(
    server_name: str,
    hours: int,
    seed: int,
    out_fh,
    start: datetime,
) -> tuple[int, int]:
    rng = random.Random(seed)
    interval = 15
    total = hours * 3600 // interval
    disk_used = rng.uniform(150, 200)

    type_cycle = CLASSES_ANOM[:]
    rng.shuffle(type_cycle)
    events = []
    i = rng.randint(20, 60)
    ev_idx = 0
    while i < total - 60:
        duration = rng.randint(40, 60)
        atype = type_cycle[ev_idx % len(type_cycle)]
        ev_idx += 1
        events.append((i, i + duration, atype))
        i += duration + rng.randint(60, 180)

    event_iter = iter(events)
    cur_event = next(event_iter, None)

    rows = 0
    anom_rows = 0
    acc: dict = {}
    for k in range(total):
        ts = start + timedelta(seconds=k * interval)
        hour = ts.hour + ts.minute / 60
        disk_used += rng.gauss(0.0008, 0.003)
        disk_used = max(50, min(380, disk_used))

        sample = _normal_sample(rng, hour, disk_used)
        active = False
        atype = None
        if cur_event and cur_event[0] <= k < cur_event[1]:
            atype = cur_event[2]
            active = True
            progress = (k - cur_event[0]) / max(1, cur_event[1] - cur_event[0])
            _apply_anomaly(sample, atype, rng, progress)
            anom_rows += 1
        elif cur_event and k >= cur_event[1]:
            cur_event = next(event_iter, None)

        accumulate_counters(sample, acc)

        sample.update({
            "timestamp": ts.isoformat(),
            "server_name": server_name,
            "anomaly_active": active,
            "anomaly_type": atype,
            "uptime_seconds": int(k * interval + rng.uniform(86_400, 864_000)),
            "cpu_per_core": [round(sample["cpu_usage_percent"] + rng.gauss(0, 3), 2)
                             for _ in range(8)],
        })
        out_fh.write(json.dumps(sample) + "\n")
        rows += 1
    return rows, anom_rows

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="tmp/ready/clean_dataset.jsonl")
    ap.add_argument("--servers", type=int, default=6)
    ap.add_argument("--hours", type=int, default=24)
    args = ap.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 5, 1)
    total_rows = 0
    total_anom = 0
    with out.open("w") as fh:
        for i in range(args.servers):
            r, a = generate_server(
                server_name=f"clean-{i+1}", hours=args.hours, seed=42 + i,
                out_fh=fh, start=start,
            )
            print(f"clean-{i+1}: {r} rows, {a} anomalous")
            total_rows += r
            total_anom += a
    print(f"Total: {total_rows} rows ({total_anom} anomalous, "
          f"{total_anom / total_rows:.1%})")

if __name__ == "__main__":
    main()
