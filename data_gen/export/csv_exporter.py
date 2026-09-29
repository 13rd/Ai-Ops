from __future__ import annotations

import csv
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, List, Optional

import pandas as pd
from sqlalchemy import and_, select

from app.models.anomaly_event import AnomalyEvent
from app.models.container import ContainerSnapshot
from app.models.metric import MetricSnapshot
from data_gen.db import SessionLocal

logger = logging.getLogger(__name__)

WINDOW_SIZE = 300
STRIDE = 4
FEATURE_COLS = [
    "cpu_percent",
    "ram_percent",
    "disk_io_bytes_per_sec",
    "network_rx_bytes",
    "container_mem_percent",
]
ANOMALY_THRESHOLD = 0.10

@dataclass
class WindowSample:
    server_id: int
    window_start: datetime
    window_end: datetime
    label: str
    features: List[List[float]]

class CSVExporter:

    def __init__(self, server_id: int, output_dir: str = "data_gen/output") -> None:
        self.server_id = server_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _load_raw_rows(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        db = SessionLocal()
        try:
            query = (
                select(MetricSnapshot)
                .where(MetricSnapshot.server_id == self.server_id)
                .order_by(MetricSnapshot.collected_at.asc())
            )
            if start:
                query = query.where(MetricSnapshot.collected_at >= start)
            if end:
                query = query.where(MetricSnapshot.collected_at <= end)

            rows = db.execute(query).scalars().all()
            if not rows:
                return pd.DataFrame()

            data = []
            for r in rows:
                cs = db.execute(
                    select(ContainerSnapshot)
                    .where(
                        and_(
                            ContainerSnapshot.server_id == self.server_id,
                            ContainerSnapshot.collected_at
                            >= r.collected_at - timedelta(seconds=20),
                            ContainerSnapshot.collected_at
                            <= r.collected_at + timedelta(seconds=20),
                        )
                    )
                    .order_by(ContainerSnapshot.collected_at.desc())
                    .limit(1)
                ).scalar_one_or_none()

                container_mem_pct: Optional[float] = None
                if cs and cs.extra_data:
                    container_mem_pct = cs.extra_data.get("memory_percentage")

                disk_io = 0.0
                if r.disk_read_bytes is not None and r.disk_write_bytes is not None:
                    disk_io = (r.disk_read_bytes + r.disk_write_bytes) / 15.0

                data.append(
                    {
                        "collected_at": r.collected_at,
                        "cpu_percent": r.cpu_usage_percent,
                        "ram_percent": r.memory_usage_percent,
                        "disk_io_bytes_per_sec": disk_io,
                        "network_rx_bytes": r.network_in_bytes,
                        "container_mem_percent": container_mem_pct,
                        "label": "normal",
                    }
                )

            return pd.DataFrame(data).set_index("collected_at").sort_index()
        finally:
            db.close()

    def _apply_labels(self, df: pd.DataFrame) -> pd.DataFrame:

        db = SessionLocal()
        try:
            events = db.execute(
                select(AnomalyEvent)
                .where(
                    and_(
                        AnomalyEvent.server_id == self.server_id,
                        AnomalyEvent.end_ts.isnot(None),
                    )
                )
                .order_by(AnomalyEvent.start_ts.asc())
            ).scalars().all()

            for event in events:
                mask = (df.index >= event.start_ts) & (df.index <= event.end_ts)
                df.loc[mask, "label"] = event.scenario_type

            return df
        finally:
            db.close()

    def _extract_windows(self, df: pd.DataFrame) -> Iterator[WindowSample]:

        feature_df = df[FEATURE_COLS]
        labels = df["label"].values
        timestamps = df.index.tolist()

        for i in range(0, len(df) - WINDOW_SIZE + 1, STRIDE):
            window = feature_df.iloc[i: i + WINDOW_SIZE]
            if window.isnull().any().any():
                continue

            window_labels = labels[i: i + WINDOW_SIZE]
            anomaly_labels = [lb for lb in window_labels if lb != "normal"]

            if len(anomaly_labels) / WINDOW_SIZE > ANOMALY_THRESHOLD:
                majority_label = Counter(anomaly_labels).most_common(1)[0][0]
            else:
                majority_label = "normal"

            yield WindowSample(
                server_id=self.server_id,
                window_start=timestamps[i],
                window_end=timestamps[i + WINDOW_SIZE - 1],
                label=majority_label,
                features=window.values.tolist(),
            )

    def export_labeled_rows(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Optional[Path]:

        df = self._load_raw_rows(start, end)
        if df.empty:
            logger.warning(f"No data found for server_id={self.server_id}")
            return None
        df = self._apply_labels(df)
        out = self.output_dir / f"labeled_rows_srv{self.server_id}.csv"
        df.reset_index().to_csv(out, index=False)
        logger.info(f"Exported {len(df)} labeled rows to {out}")
        return out

    def export_windows(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Optional[Path]:

        df = self._load_raw_rows(start, end)
        if df.empty:
            logger.warning(f"No data found for server_id={self.server_id}")
            return None
        df = self._apply_labels(df)

        out = self.output_dir / f"windows_srv{self.server_id}.csv"
        header = ["window_start", "window_end", "server_id", "label"]
        for t in range(WINDOW_SIZE):
            for feat in FEATURE_COLS:
                header.append(f"{feat}_t{t}")

        count = 0
        with open(out, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for sample in self._extract_windows(df):
                row: list = [
                    sample.window_start.isoformat(),
                    sample.window_end.isoformat(),
                    sample.server_id,
                    sample.label,
                ]
                for t_features in sample.features:
                    row.extend(t_features)
                writer.writerow(row)
                count += 1

        logger.info(f"Exported {count} windows to {out}")
        return out
