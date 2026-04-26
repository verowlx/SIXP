from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Flask, redirect, render_template, request, url_for
from tinydb import Query, TinyDB


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
TRAFFIC_MONITOR_DIR = REPO_ROOT / "trafficmonitor"
if str(TRAFFIC_MONITOR_DIR) not in sys.path:
    sys.path.insert(0, str(TRAFFIC_MONITOR_DIR))

from snmp_monitor import monitor_interface_bandwidth  # noqa: E402


app = Flask(__name__)
db = TinyDB(BASE_DIR / "policy_manager_db.json")
config_table = db.table("config")
samples_table = db.table("samples")


class PollingService:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._status = "idle"
        self._last_error: Optional[str] = None

    def start(self, config: Dict[str, Any]) -> None:
        self.stop()
        self._stop_event.clear()
        self._status = "running"
        self._last_error = None
        self._thread = threading.Thread(
            target=self._run_loop, args=(config,), daemon=True, name="snmp-poller"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        if self._status != "error":
            self._status = "stopped"

    def status(self) -> Dict[str, Optional[str]]:
        return {"state": self._status, "last_error": self._last_error}

    def _run_loop(self, config: Dict[str, Any]) -> None:
        while not self._stop_event.is_set():
            started_at = datetime.now(timezone.utc)
            try:
                sample = monitor_interface_bandwidth(
                    host=config["host"],
                    community=config["community"],
                    if_index=config["if_index"],
                    interval_seconds=config["sample_window_seconds"],
                    port=config["port"],
                    timeout=config["timeout"],
                    retries=config["retries"],
                )
                samples_table.insert(
                    {
                        "timestamp_utc": started_at.isoformat(),
                        "host": config["host"],
                        "if_index": config["if_index"],
                        "in_bps": sample.in_bps,
                        "out_bps": sample.out_bps,
                        "interface_speed_bps": sample.interface_speed_bps,
                        "in_utilization_pct": sample.in_utilization_pct,
                        "out_utilization_pct": sample.out_utilization_pct,
                        "sample_window_seconds": sample.interval_seconds,
                    }
                )
                self._status = "running"
                self._last_error = None
            except Exception as exc:  # broad catch to keep service alive
                self._status = "error"
                self._last_error = str(exc)

            wait_seconds = max(
                float(config["poll_interval_seconds"])
                - float(config["sample_window_seconds"]),
                0.0,
            )
            if self._stop_event.wait(wait_seconds):
                break


poller = PollingService()


def _latest_config() -> Dict[str, Any]:
    config = config_table.get(Query().id == "active")
    if config:
        return config
    return {
        "id": "active",
        "host": "",
        "community": "public",
        "if_index": 1,
        "port": 161,
        "timeout": 2,
        "retries": 1,
        "sample_window_seconds": 5.0,
        "poll_interval_seconds": 10.0,
    }


@app.route("/", methods=["GET"])
def index() -> str:
    config = _latest_config()
    latest_samples = samples_table.all()[-25:]
    latest_samples.reverse()
    return render_template(
        "index.html",
        config=config,
        poller_status=poller.status(),
        samples=latest_samples,
    )


@app.route("/start", methods=["POST"])
def start_monitoring():
    config = {
        "id": "active",
        "host": request.form["host"].strip(),
        "community": request.form["community"].strip(),
        "if_index": int(request.form["if_index"]),
        "port": int(request.form["port"]),
        "timeout": int(request.form["timeout"]),
        "retries": int(request.form["retries"]),
        "sample_window_seconds": float(request.form["sample_window_seconds"]),
        "poll_interval_seconds": float(request.form["poll_interval_seconds"]),
    }
    config_table.upsert(config, Query().id == "active")
    poller.start(config)
    return redirect(url_for("index"))


@app.route("/stop", methods=["POST"])
def stop_monitoring():
    poller.stop()
    return redirect(url_for("index"))


@app.route("/clear", methods=["POST"])
def clear_samples():
    samples_table.truncate()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
