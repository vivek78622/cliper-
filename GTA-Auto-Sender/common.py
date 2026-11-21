"""Shared helpers for clip_feeder.py and autopost.py (config, .env, time zone, log)."""
import datetime as dt, json, os, sys
from pathlib import Path

ROOT = os.path.dirname(os.path.abspath(__file__))
Q = Path(ROOT) / "queue"
API = "https://zernio.com/api/v1"


def load_config():
    path = os.path.join(ROOT, "config", "channels.json")
    if not os.path.exists(path):
        sys.exit("config/channels.json missing: copy config/channels.example.json to config/channels.json and fill it in.")
    try:
        return json.load(open(path, encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        sys.exit(f"config/channels.json is not valid JSON ({e}). In JSON write Windows paths with forward slashes "
                 "(C:/videos/output) or doubled backslashes (C:\\\\videos\\\\output).")


def tzinfo(cfg):
    sign = -1 if cfg.get("utc_offset", "+00:00").startswith("-") else 1
    h, m = cfg.get("utc_offset", "+00:00").lstrip("+-").split(":")
    return dt.timezone(sign * dt.timedelta(hours=int(h), minutes=int(m)))


def load_env():
    d = {}
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8-sig"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.strip().split("=", 1)
                d[k] = v
    return d


def read_json(path):
    """utf-8-sig: a file saved with a byte-order mark (PowerShell's default) must not crash the run."""
    return json.load(open(path, encoding="utf-8-sig"))


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:  # no BOM
        json.dump(obj, f, indent=2, ensure_ascii=False)


def make_logger(tz, name):
    os.makedirs(Q, exist_ok=True)

    def log(msg):
        line = dt.datetime.now(tz).strftime("%d %b %H:%M:%S ") + msg
        print(line.encode("ascii", "replace").decode())   # emoji-safe on any Windows console
        with open(os.path.join(Q, name), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    return log
