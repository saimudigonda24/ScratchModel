import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load_env(path: Path | None = None) -> None:
    """Load .env values without overriding already-exported environment vars."""
    env_path = path or ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

