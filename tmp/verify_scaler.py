import joblib, numpy as np
from ml.config import FEATURE_COLS
sc = joblib.load("models/scalers/clean-1.pkl")
print(f"{'feature':<26}{'mean_':>16}{'scale_(std)':>16}")
for f, m, s in zip(FEATURE_COLS, sc.mean_, sc.scale_):
    flag = "  <-- RATE" if "bps" in f else ""
    print(f"{f:<26}{m:>16.4f}{s:>16.6f}{flag}")

print("\nWhat a REAL web server (2 MB/s in, 1.5 MB/s out, 5 MB/s disk write) scales to:")
real = {"disk_read_bps":3_000_000, "disk_write_bps":5_000_000,
        "net_in_bps":2_000_000, "net_out_bps":1_500_000}
idx = {f:i for i,f in enumerate(FEATURE_COLS)}
for f,v in real.items():
    i = idx[f]
    z = (v - sc.mean_[i]) / sc.scale_[i]
    print(f"  {f:<16} raw={v:>12,}  ->  scaled z = {z:,.1f} sigma")
