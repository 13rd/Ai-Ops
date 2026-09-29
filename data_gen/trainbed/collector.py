#!/usr/bin/env python3

import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

_TRAINBED_DB_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg2://trainbed:trainbed@postgres:5432/trainbed")
os.environ["DATABASE_URL"] = _TRAINBED_DB_URL.replace("+psycopg2", "+asyncpg")

from data_gen.export.csv_exporter import WINDOW_SIZE, STRIDE, FEATURE_COLS, ANOMALY_THRESHOLD
from data_gen.trainbed.profiles import PROFILES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("collector")

OUTPUT_DIR = Path("data_gen/output")

def _extract_windows(df: pd.DataFrame) -> list[dict]:
    windows = []
    labels = df["label"].values
    feature_data = df[FEATURE_COLS].values
    timestamps = df.index.tolist()
    n = len(df)
    for i in range(0, n - WINDOW_SIZE + 1, STRIDE):
        window = feature_data[i:i + WINDOW_SIZE]
        if pd.isna(window).any():
            continue
        win_labels = labels[i:i + WINDOW_SIZE]
        anomaly = [lb for lb in win_labels if lb != "normal"]
        if len(anomaly) / WINDOW_SIZE > ANOMALY_THRESHOLD:
            from collections import Counter
            label = Counter(anomaly).most_common(1)[0][0]
        else:
            label = "normal"
        windows.append({
            "window_start": timestamps[i].isoformat(),
            "window_end": timestamps[i + WINDOW_SIZE - 1].isoformat(),
            "label": label,
            "features": window.values.tolist(),
        })
    return windows

def _load_labeled(engine, server_id: int) -> pd.DataFrame:
    metrics = pd.read_sql(
        f"SELECT * FROM metric_snapshots WHERE server_id = {server_id} ORDER BY collected_at ASC",
        engine, parse_dates=["collected_at"], index_col="collected_at",
    )
    if metrics.empty:
        return pd.DataFrame()

    events = pd.read_sql(
        f"SELECT * FROM anomaly_events WHERE server_id = {server_id} AND end_ts IS NOT NULL "
        f"ORDER BY start_ts ASC",
        engine, parse_dates=["start_ts", "end_ts"],
    )

    metrics["label"] = "normal"
    for _, ev in events.iterrows():
        mask = (metrics.index >= ev["start_ts"]) & (metrics.index <= ev["end_ts"])
        metrics.loc[mask, "label"] = ev["scenario_type"]

    cs_df = pd.read_sql(
        f"SELECT collected_at, extra_data FROM container_snapshots "
        f"WHERE server_id = {server_id} ORDER BY collected_at ASC",
        engine, parse_dates=["collected_at"],
    )
    if not cs_df.empty:
        container_mem = []
        cs_by_ts = {}
        for _, row in cs_df.iterrows():
            ed = row["extra_data"]
            if isinstance(ed, str):
                import json as _j
                ed = _j.loads(ed)
            cs_by_ts[row["collected_at"]] = (ed or {}).get("memory_percentage")
        for ts in metrics.index:
            nearest = min(cs_by_ts.keys(), key=lambda x: abs((x - ts).total_seconds())) if cs_by_ts else None
            if nearest and abs((nearest - ts).total_seconds()) <= 20:
                container_mem.append(cs_by_ts[nearest])
            else:
                container_mem.append(None)
        metrics["container_mem_percent"] = container_mem
    else:
        metrics["container_mem_percent"] = None

    features = pd.DataFrame(index=metrics.index)
    features["cpu_percent"] = metrics["cpu_usage_percent"]
    features["ram_percent"] = metrics["memory_usage_percent"]
    features["disk_io_bytes_per_sec"] = (
        metrics["disk_read_bytes"].fillna(0) + metrics["disk_write_bytes"].fillna(0)
    ) / 15.0
    features["network_rx_bytes"] = metrics["network_in_bytes"]
    features["container_mem_percent"] = metrics["container_mem_percent"]
    features["label"] = metrics["label"]
    features["server_id"] = server_id
    return features

def collect(engine) -> dict:
    summary = {}
    all_labeled = []
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for pname, profile in PROFILES.items():
        sid = profile.server_id
        logger.info("Exporting server %d (%s)...", sid, profile.label)
        df = _load_labeled(engine, sid)
        if df.empty:
            logger.warning("  No data for server %d, skipping", sid)
            continue

        labeled_path = OUTPUT_DIR / f"labeled_rows_srv{sid}.csv"
        df.reset_index().to_csv(labeled_path, index=False)
        logger.info("  Labeled rows: %d -> %s", len(df), labeled_path)

        clean = df.dropna(subset=FEATURE_COLS)
        windows = _extract_windows(clean) if len(clean) >= WINDOW_SIZE else []
        if windows:
            win_path = OUTPUT_DIR / f"windows_srv{sid}.csv"
            import csv
            with open(win_path, "w", newline="") as f:
                header = ["window_start", "window_end", "server_id", "label"]
                for t in range(WINDOW_SIZE):
                    for feat in FEATURE_COLS:
                        header.append(f"{feat}_t{t}")
                writer = csv.writer(f)
                writer.writerow(header)
                for w in windows:
                    row = [w["window_start"], w["window_end"], sid, w["label"]]
                    for t_feat in w["features"]:
                        row.extend(t_feat)
                    writer.writerow(row)
            logger.info("  Windows: %d -> %s", len(windows), win_path)

        dist = df["label"].value_counts().to_dict()
        summary[sid] = {
            "name": profile.label,
            "rows": int(len(df)),
            "windows": len(windows),
            "labels": {k: int(v) for k, v in dist.items()},
        }
        df["source_server"] = sid
        all_labeled.append(df)

    if all_labeled:
        merged = pd.concat(all_labeled, ignore_index=False)
        merged_path = OUTPUT_DIR / "all_servers_merged.csv"
        merged.reset_index().to_csv(merged_path, index=False)
        logger.info("Merged: %d rows -> %s", len(merged), merged_path)

    summary_path = OUTPUT_DIR / "training_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    logger.info("Summary -> %s", summary_path)

    total_rows = total_wins = total_norm = total_anom = 0
    print("\n===== TRAINING DATA SUMMARY =====")
    print(f"{'Server':<20} {'Rows':>8} {'Windows':>8} {'Normal':>8} {'Anomaly':>8}")
    print("-" * 52)
    for sid, s in sorted(summary.items()):
        anom = sum(v for k, v in s["labels"].items() if k != "normal")
        norm = s["labels"].get("normal", 0)
        print(f"{s['name']:<20} {s['rows']:>8} {s['windows']:>8} {norm:>8} {anom:>8}")
        total_rows += s["rows"]
        total_wins += s["windows"]
        total_norm += norm
        total_anom += anom
    print("-" * 52)
    print(f"{'TOTAL':<20} {total_rows:>8} {total_wins:>8} {total_norm:>8} {total_anom:>8}")
    print("=" * 52)
    return summary

if __name__ == "__main__":
    engine = create_engine(_TRAINBED_DB_URL)
    collect(engine)
