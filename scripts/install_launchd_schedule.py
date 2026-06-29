from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portfolio_warehouse.settings import get_settings


LABEL = "com.mbailey.portfolio-warehouse"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install or remove the local launchd schedule.")
    parser.add_argument("--uninstall", action="store_true", help="Unload and remove the launchd plist.")
    parser.add_argument("--start-now", action="store_true", help="Kick off the job immediately after install.")
    return parser.parse_args(argv[1:])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv)
    settings = get_settings()
    root = Path(__file__).resolve().parents[1]
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"

    if args.uninstall:
        _unload(plist_path)
        if plist_path.exists():
            plist_path.unlink()
            print(f"Removed {plist_path}")
        return 0

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable,
            str(root / "scripts" / "run_pipeline.py"),
            "--notify-success",
        ],
        "WorkingDirectory": str(root),
        "StartCalendarInterval": {
            "Hour": settings.schedule_hour,
            "Minute": settings.schedule_minute,
        },
        "StandardOutPath": str(settings.log_dir / "launchd.out.log"),
        "StandardErrorPath": str(settings.log_dir / "launchd.err.log"),
        "RunAtLoad": False,
    }
    plist_path.write_bytes(plistlib.dumps(payload, sort_keys=False))
    _unload(plist_path)
    _run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist_path)], check=True)
    _run(["launchctl", "enable", f"gui/{os.getuid()}/{LABEL}"], check=True)
    print(f"Installed {LABEL} at {settings.schedule_hour:02d}:{settings.schedule_minute:02d} daily")
    print(f"Plist: {plist_path}")
    print(f"Pipeline log: {settings.log_dir / 'pipeline.log'}")
    if args.start_now:
        _run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{LABEL}"], check=True)
        print("Started scheduled job now.")
    return 0


def _unload(plist_path: Path) -> None:
    _run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist_path)], check=False)


def _run(command: list[str], *, check: bool) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=check, text=True, capture_output=True)


if __name__ == "__main__":
    raise SystemExit(main())
