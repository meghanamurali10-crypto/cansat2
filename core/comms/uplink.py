"""
Uplink command builder.

Every command from the ground station is wrapped as:
    <CMD>,<SEQ>,<CHECKSUM>
where CHECKSUM = XOR of all bytes in "<CMD>,<SEQ>".

Firmware validates CHECKSUM before acting on the command.
"""
from core.telemetry.constants import TEAM_ID

_seq_counter = 0


def _checksum(s: str) -> str:
    """XOR of all bytes, returned as 4-digit hex."""
    c = 0
    for b in s.encode("ascii"):
        c ^= b
    return f"{c:04X}"


def _next_seq() -> int:
    global _seq_counter
    _seq_counter = (_seq_counter + 1) % 10000
    return _seq_counter


def build(command: str, *args) -> str:
    """
    Build a framed uplink line.

    Examples
    --------
    build("TXON")                -> "TXON,1,ABCD\\n"
    build("SET_TARGET", 28.6, 77.2) -> "SET_TARGET,2,1234,28.600000,77.200000\\n"
    """
    cmd = command.strip().upper()
    seq = _next_seq()

    if args:
        # Arguments are appended as comma-separated values
        arg_str = ",".join(
            f"{a:.6f}" if isinstance(a, float) else str(a)
            for a in args
        )
        payload = f"{cmd},{seq},{arg_str}"
    else:
        payload = f"{cmd},{seq}"

    cs = _checksum(payload)
    return f"{payload},{cs}\n"


def reset_sequence():
    """Reset the sequence counter (for tests)."""
    global _seq_counter
    _seq_counter = 0
