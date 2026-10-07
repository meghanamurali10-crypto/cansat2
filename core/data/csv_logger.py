"""
CSV logger — writes header from FIELD_NAMES, one row per packet,
flushes after each row so nothing is lost on crash.

Filename: logs/csv/Flight_<TEAM_ID>_<timestamp>.csv
"""
import csv
import os
import threading
from datetime import datetime

from core.telemetry.constants import FIELD_NAMES, TEAM_ID
from utils.logger import get_logger

logger = get_logger(__name__)


class CSVLogger:
    def __init__(self, out_dir: str = None):
        if out_dir is None:
            root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))))
            out_dir = os.path.join(root, "logs", "csv")
        os.makedirs(out_dir, exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_tid = TEAM_ID.replace("/", "_").replace("\\", "_")
        self.filepath = os.path.join(
            out_dir, f"Flight_{safe_tid}_{stamp}.csv")

        self._lock = threading.Lock()
        self._fh = open(self.filepath, "w", newline="")
        self._writer = csv.writer(self._fh, quoting=csv.QUOTE_MINIMAL)
        self._writer.writerow(FIELD_NAMES)
        self._fh.flush()
        self.packet_count = 0
        logger.info(f"CSVLogger opened {self.filepath}")

    def log(self, packet):
        with self._lock:
            if self._fh is None:
                return
            row = [packet.get(col, "") for col in FIELD_NAMES]
            row = ["" if v is None else v for v in row]
            self._writer.writerow(row)
            self._fh.flush()   # crash-safe
            self.packet_count += 1

    def log_marker(self, text: str):
        with self._lock:
            if self._fh is None:
                return
            self._writer.writerow([f"# {text}"])
            self._fh.flush()

    def close(self):
        with self._lock:
            if self._fh:
                try:
                    self._fh.close()
                except Exception:
                    pass
                self._fh = None