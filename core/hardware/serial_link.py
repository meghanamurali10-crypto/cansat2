"""
Serial link — threaded reader/writer for the LoRa receiver.

Handles:
  - Auto-reconnect when the USB device disconnects mid-flight
  - Windows ClearCommError quirk (PermissionError 13)
  - Thread-safe read buffer
"""
import threading
import time
from collections import deque

import serial
from serial.tools import list_ports

from utils.logger import get_logger

logger = get_logger(__name__)


_GS_PORT_HINTS = (
    "CP210", "CP2102", "CP2104",
    "CH340", "CH341",
    "FT232", "FTDI",
    "Silicon Labs",
    "USB Serial",
    "USB-SERIAL",
    "Prolific",
    "PL2303",
    "LoRa", "E220", "E32",
)


def list_available_ports():
    out = []
    for p in list_ports.comports():
        desc = p.description or p.product or "Unknown"
        out.append((p.device, desc))
    return out


def guess_gs_port():
    ports = list_ports.comports()
    if not ports:
        return None
    if len(ports) == 1:
        return ports[0].device

    scored = []
    for p in ports:
        text = f"{p.description or ''} {p.product or ''} {p.manufacturer or ''}".upper()
        score = 0
        for i, hint in enumerate(_GS_PORT_HINTS):
            if hint.upper() in text:
                score = max(score, len(_GS_PORT_HINTS) - i)
        scored.append((score, p.device))

    scored.sort(reverse=True)
    if scored and scored[0][0] > 0:
        return scored[0][1]
    return ports[0].device


class SerialLink:
    def __init__(self, port: str, baud: int = 115200,
                 read_timeout_s: float = 0.1,
                 max_buffer: int = 10000,
                 auto_reconnect: bool = True,
                 reconnect_interval_s: float = 2.0):
        self.port = port
        self.baud = baud
        self.read_timeout_s = read_timeout_s
        self.max_buffer = max_buffer
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval_s = reconnect_interval_s

        self._serial = None
        self._reader_thread = None
        self._stop_event = threading.Event()
        self._lines = deque(maxlen=max_buffer)
        self._lock = threading.Lock()

        self._connected = False
        self._last_error = None
        self._rx_count = 0
        self._reconnect_count = 0

    # -----------------------------------------------------------------
    def connect(self):
        if self._connected:
            return
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.read_timeout_s,
            )
        except serial.SerialException as e:
            self._last_error = str(e)
            logger.error(f"Cannot open {self.port}@{self.baud}: {e}")
            raise

        self._stop_event.clear()
        self._connected = True
        self._reader_thread = threading.Thread(
            target=self._read_loop,
            name=f"SerialLink-{self.port}",
            daemon=True,
        )
        self._reader_thread.start()
        logger.info(f"SerialLink opened {self.port} @ {self.baud} baud")

    def disconnect(self):
        self._stop_event.set()
        t = self._reader_thread
        if t is not None:
            t.join(timeout=2.0)
        self._reader_thread = None
        self._close_port()
        self._connected = False
        logger.info(f"SerialLink closed {self.port}")

    def is_connected(self) -> bool:
        return self._connected and self._serial is not None and self._serial.is_open

    # -----------------------------------------------------------------
    def _close_port(self):
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    def _reopen(self) -> bool:
        """Try to reopen the port. Returns True on success."""
        self._close_port()
        for attempt in range(3):
            try:
                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baud,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=self.read_timeout_s,
                )
                self._reconnect_count += 1
                logger.info(f"SerialLink reconnected to {self.port} "
                            f"(attempt {attempt + 1})")
                return True
            except serial.SerialException as e:
                logger.warning(f"Reconnect attempt {attempt + 1} failed: {e}")
                time.sleep(0.5)
        return False

    # -----------------------------------------------------------------
    def _read_loop(self):
        buf = bytearray()

        while not self._stop_event.is_set():
            # If port died, attempt reconnect
            if self._serial is None or not getattr(self._serial, "is_open", False):
                if self.auto_reconnect:
                    if not self._reopen():
                        logger.error("Auto-reconnect failed — giving up")
                        self._connected = False
                        return
                    buf = bytearray()
                else:
                    self._connected = False
                    return

            try:
                chunk = self._serial.read(256)
            except serial.SerialException as e:
                # This is where ClearCommError shows up
                self._last_error = str(e)
                logger.warning(f"Serial read error (will reconnect): {e}")
                self._close_port()
                if not self.auto_reconnect:
                    self._connected = False
                    return
                time.sleep(self.reconnect_interval_s)
                continue
            except OSError as e:
                # Windows PermissionError(13) sometimes leaks through here
                self._last_error = str(e)
                logger.warning(f"OS-level serial error (will reconnect): {e}")
                self._close_port()
                if not self.auto_reconnect:
                    self._connected = False
                    return
                time.sleep(self.reconnect_interval_s)
                continue
            except Exception as e:
                self._last_error = str(e)
                logger.error(f"Unexpected serial error: {e}")
                self._close_port()
                time.sleep(self.reconnect_interval_s)
                continue

            if not chunk:
                continue

            buf.extend(chunk)
            while b"\n" in buf:
                line, _, rest = buf.partition(b"\n")
                buf = bytearray(rest)
                self._push_line(line)

            if len(buf) > 4096:
                self._push_line(buf)
                buf = bytearray()

        logger.debug("Serial reader thread exited")

    def _push_line(self, raw: bytes):
        try:
            text = raw.decode("ascii", errors="ignore").strip().rstrip("\r")
        except Exception:
            return
        if not text:
            return
        with self._lock:
            self._lines.append(text)
            self._rx_count += 1

    # -----------------------------------------------------------------
    def read_available_lines(self):
        with self._lock:
            if not self._lines:
                return []
            out = list(self._lines)
            self._lines.clear()
            return out

    def send_command(self, line: str):
        if not self.is_connected():
            logger.warning("send_command called while not connected")
            return False
        if not line.endswith("\n"):
            line = line + "\n"
        try:
            self._serial.write(line.encode("ascii", errors="ignore"))
            self._serial.flush()
            logger.debug(f"TX: {line.strip()}")
            return True
        except serial.SerialException as e:
            logger.warning(f"Serial write failed (port will reconnect): {e}")
            self._close_port()
            return False
        except Exception as e:
            logger.error(f"Serial write error: {e}")
            return False

    def stats(self):
        return {
            "port": self.port,
            "baud": self.baud,
            "connected": self.is_connected(),
            "rx_count": self._rx_count,
            "buffered": len(self._lines),
            "reconnect_count": self._reconnect_count,
            "last_error": self._last_error,
        }
