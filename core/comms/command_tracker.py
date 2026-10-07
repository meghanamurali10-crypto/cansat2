"""
Command tracker — matches sent commands with ACK echoes from the CanSat.

Usage:
    tracker = CommandTracker(timeout_s=5.0)
    tracker.sent(seq=42, name="CAL")

    # Every time an echo arrives:
    tracker.ack(seq=42)

    # Periodically poll for timeouts:
    for seq, name in tracker.timed_out():
        print(f"Command {name} (seq {seq}) not acknowledged")
"""
import time


class CommandTracker:
    def __init__(self, timeout_s: float = 5.0):
        self.timeout_s = timeout_s
        self._pending = {}     # seq -> (name, sent_monotonic)

    def sent(self, seq: int, name: str):
        self._pending[int(seq)] = (name, time.monotonic())

    def ack(self, seq: int) -> bool:
        """Mark seq as acknowledged. Returns True if it was pending."""
        return self._pending.pop(int(seq), None) is not None

    def timed_out(self):
        """Return list of (seq, name) that have exceeded timeout_s."""
        now = time.monotonic()
        expired = [
            (seq, name)
            for seq, (name, t) in self._pending.items()
            if now - t > self.timeout_s
        ]
        for seq, _ in expired:
            self._pending.pop(seq, None)
        return expired

    def pending_count(self) -> int:
        return len(self._pending)

    def clear(self):
        self._pending.clear()
