"""
Telemetry packet parser — 37-field format.

Handles:
  * Blank numeric fields (stores None instead of raising)
  * LoRa receiver wrappers: [RSSI:-85], <START>, $S,
  * Pressure conversion (hPa -> Pa)
  * TEAM_ID validation
"""
import re
from dataclasses import dataclass, field as _field

from core.telemetry.constants import (
    FIELD_NAMES, FLOAT_FIELDS, INT_FIELDS, TRIPLET_FIELDS,
    TEAM_ID, FIELD_ALIASES, FLIGHT_STATES, pressure_to_pa,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class PacketParseError(Exception):
    pass


@dataclass
class TelemetryPacket:
    raw_line: str
    fields: dict = _field(default_factory=dict)

    def get(self, name, default=None):
        v = self.fields.get(name, default)
        return default if v is None else v

    def __getattr__(self, name):
        if name.startswith("_") or name in ("fields", "raw_line"):
            raise AttributeError(name)
        fields = self.__dict__.get("fields", {})
        if name in fields:
            return fields[name]
        raise AttributeError(name)


# -----------------------------------------------------------------
# LoRa receiver wrapper stripping
# -----------------------------------------------------------------
_WRAPPER_PREFIXES = (
    "RSSI:", "SNR:", "PING", "CMD_ECHO", "CALIBRATION_COMPLETE",
    "CALIBRATION_FAILED", "#", "CAL_",
)


def strip_receiver_wrapper(line: str):
    """Strip [RSSI:...], <START>, $S,, etc. Returns None if not telemetry."""
    if not line:
        return None
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith(_WRAPPER_PREFIXES):
        return None
    # Remove leading "[...]" wrapper
    stripped = re.sub(r"^\[[^\]]*\]\s*", "", stripped)
    # Remove common frame markers
    stripped = re.sub(r"^(<START>|\$TELEM,|\$S,|\$T,)", "", stripped)
    # Remove trailing markers
    stripped = re.sub(r"(<END>|\r)$", "", stripped).strip()
    return stripped or None


# -----------------------------------------------------------------
# Team ID check — accept both full and short formats
# -----------------------------------------------------------------
def _team_id_matches(received) -> bool:
    if received is None:
        return False
    s = str(received).strip()
    if s == TEAM_ID:
        return True
    # Accept "1234" if TEAM_ID ends with "-1234"
    short = TEAM_ID.split("-")[-1]
    if s == short:
        return True
    if s.endswith(f"-{short}"):
        return True
    return False


# -----------------------------------------------------------------
# Parse one line
# -----------------------------------------------------------------
def parse_packet(line: str, pressure_unit: str = "hPa") -> TelemetryPacket:
    raw = strip_receiver_wrapper(line)
    if raw is None:
        raise PacketParseError("Not a telemetry line")

    parts = [p.strip() for p in raw.split(",")]

    # Pad short packets, truncate long ones
    if len(parts) < len(FIELD_NAMES):
        parts += [""] * (len(FIELD_NAMES) - len(parts))
    elif len(parts) > len(FIELD_NAMES):
        parts = parts[:len(FIELD_NAMES)]

    fields = {}
    for name, value in zip(FIELD_NAMES, parts):
        if value == "":
            fields[name] = None
            continue

        if name in TRIPLET_FIELDS:
            # Legacy support only
            fields[name] = value
            continue

        if name in FLOAT_FIELDS:
            try:
                fields[name] = float(value)
            except (ValueError, TypeError):
                fields[name] = None
        elif name in INT_FIELDS:
            try:
                fields[name] = int(value)
            except (ValueError, TypeError):
                fields[name] = None
        else:
            fields[name] = value

    # Convert pressure to Pa (SI per guidelines)
    if fields.get("PRESSURE") is not None:
        fields["PRESSURE_RAW"] = fields["PRESSURE"]
        fields["PRESSURE"] = pressure_to_pa(fields["PRESSURE"], pressure_unit)

    # TEAM_ID check (soft — mismatch raises so caller can log)
    tid = fields.get("TEAM_ID")
    if tid is not None and not _team_id_matches(tid):
        raise PacketParseError(f"TEAM_ID mismatch: {tid!r}")

    return TelemetryPacket(raw_line=raw, fields=fields)


# -----------------------------------------------------------------
# Add legacy aliases and human-readable state name
# -----------------------------------------------------------------
def add_legacy_aliases(packet: TelemetryPacket) -> TelemetryPacket:
    for old_key, new_key in FIELD_ALIASES.items():
        if new_key in packet.fields and old_key not in packet.fields:
            packet.fields[old_key] = packet.fields[new_key]

    state_num = packet.fields.get("FLIGHT_SOFTWARE_STATE")
    if state_num is not None:
        try:
            packet.fields["FLIGHT_STATE_NAME"] = FLIGHT_STATES.get(
                int(state_num), f"STATE_{state_num}"
            )
        except (ValueError, TypeError):
            packet.fields["FLIGHT_STATE_NAME"] = str(state_num)

    return packet