"""
Simulation engine — generates synthetic 37-field telemetry packets.

Used when no hardware is connected, for training, demos, and testing
the ground-station pipeline end-to-end.

Public API:
    engine = SimulationEngine(packet_callback=cb, team_id=TEAM_ID)
    engine.start(scenario="nominal", rate_hz=1.0)
    engine.stop()
    engine.is_running()

Scenarios:
    nominal          — normal flight profile
    gnss_loss        — GNSS fix drops mid-descent (fix=0, sats=0)
    power_fault      — voltage collapses after deployment
    flywheel_stall   — HALL_RPM drops to 0 during descent
    comm_loss        — periodic 3-second gaps in packet stream
"""
import math
import random
import threading
import time
from datetime import datetime, timezone

from core.telemetry.constants import TEAM_ID, FLIGHT_STATES
from utils.logger import get_logger

logger = get_logger(__name__)


# -----------------------------------------------------------------
# Flight-state numbers (must match firmware / constants.py)
# -----------------------------------------------------------------
STATE_BOOT               = 0
STATE_TEST_MODE          = 1
STATE_LAUNCH_PAD         = 2
STATE_ASCENT             = 3
STATE_ROCKET_DEPLOY      = 4
STATE_DESCENT            = 5
STATE_AEROBREAK_RELEASE  = 6
STATE_IMPACT             = 7


class SimulationEngine:
    """
    Emits synthetic 37-field telemetry lines to a callback.

    The callback receives a single CSV line (string) identical in
    format to what the LoRa receiver would deliver — so the packet
    parser and everything downstream stay identical between sim and
    real hardware.
    """

    def __init__(self, packet_callback=None, team_id: str = TEAM_ID,
                 seed: int = None):
        """
        Parameters
        ----------
        packet_callback : callable(str)
            Called for every generated line. Fires on the worker thread —
            the callback must be thread-safe (MainWindow._inject_packet
            is, because it just pushes to Qt via a queued signal path
            or direct call on the main loop).
        team_id : str
            Team identifier — defaults to constants.TEAM_ID.
        seed : int, optional
            RNG seed for reproducible runs.
        """
        self.callback = packet_callback
        self.team_id = team_id
        self._rng = random.Random(seed)

        # Runtime state
        self.packet_count = 0
        self.synthetic_time = 0.0          # seconds since sim start
        self.scenario = "nominal"
        self.rate_hz = 1.0

        self._thread = None
        self._stop_event = threading.Event()
        self._running = False
        self._lock = threading.Lock()

        # Launch reference — Delhi region, matches guidance reference
        self.launch_lat = 28.6131
        self.launch_lon = 77.2290
        self.launch_alt_msl = 216.0        # metres above sea level

        # GNSS drift model (small walk during flight)
        self._gnss_lat = self.launch_lat
        self._gnss_lon = self.launch_lon
        self._gnss_alt = self.launch_alt_msl

        # Fault bookkeeping
        self._last_comm_gap = 0.0

        logger.info(f"SimulationEngine created (team_id={self.team_id})")

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------
    def start(self, scenario: str = "nominal", rate_hz: float = 1.0):
        """Start emitting packets. No-op if already running."""
        with self._lock:
            if self._running:
                logger.warning("Simulation already running — ignoring start()")
                return
            self.scenario = scenario
            self.rate_hz = max(0.1, float(rate_hz))
            self.packet_count = 0
            self.synthetic_time = 0.0
            self._gnss_lat = self.launch_lat
            self._gnss_lon = self.launch_lon
            self._gnss_alt = self.launch_alt_msl
            self._last_comm_gap = 0.0
            self._stop_event.clear()
            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop, name="SimEngine", daemon=True)
            self._thread.start()
        logger.info(f"Simulation started: scenario={scenario} "
                    f"rate={self.rate_hz:.1f} Hz")

    def stop(self):
        """Stop emitting packets. Blocks until the worker thread exits."""
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()
            t = self._thread
            self._running = False
        if t is not None:
            t.join(timeout=3.0)
        logger.info("Simulation stopped")

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    # -----------------------------------------------------------------
    # Worker loop
    # -----------------------------------------------------------------
    def _run_loop(self):
        period = 1.0 / self.rate_hz
        next_tick = time.monotonic()
        try:
            while not self._stop_event.is_set():
                line = self._generate_synthetic_packet()

                # End of mission — stop cleanly
                if line is None:
                    logger.info("Simulation mission complete — stopping")
                    break

                # Comm-loss scenario: skip emitting during gaps
                if self.scenario == "comm_loss":
                    now_s = self.synthetic_time
                    # 3-second blackouts at t=20s and t=45s
                    in_gap = (
                        (20.0 <= now_s < 23.0) or
                        (45.0 <= now_s < 48.0)
                    )
                    if in_gap:
                        self.packet_count -= 1     # don't count skipped packets
                        next_tick += period
                        self._stop_event.wait(
                            max(0.0, next_tick - time.monotonic()))
                        continue

                if self.callback is None:
                    continue
                try:
                    self.callback(line)
                except Exception:
                    logger.exception("Simulation callback raised")

                next_tick += period
                sleep_for = next_tick - time.monotonic()
                if sleep_for > 0:
                    self._stop_event.wait(sleep_for)
                else:
                    # Fell behind — resync to avoid burst catch-up
                    next_tick = time.monotonic()

        except Exception:
            logger.exception("Simulation loop crashed")
        finally:
            with self._lock:
                self._running = False
            logger.debug("Simulation worker exited")

    # -----------------------------------------------------------------
    # Packet generation
    # -----------------------------------------------------------------
    def _generate_synthetic_packet(self):
        """
        Build one comma-separated 37-field telemetry line.

        Field order (see core/telemetry/constants.py):
          TEAM_ID, TIMESTAMP, PACKET_COUNT, ALTITUDE, PRESSURE, TEMP,
          VOLTAGE, GNSS_TIME, GNSS_LATITUDE, GNSS_LONGITUDE,
          GNSS_ALTITUDE, GNSS_SATS, ACCEL_X, ACCEL_Y, ACCEL_Z,
          GYRO_X, GYRO_Y, GYRO_Z, MAG_X, MAG_Y, MAG_Z,
          ROLL, PITCH, YAW, LIGHT_LUX, UV_INDEX, HALL_RPM,
          FLIGHT_SOFTWARE_STATE, REL_ALTITUDE, VERTICAL_SPEED,
          GNSS_GROUND_SPEED, GNSS_COURSE, GNSS_HDOP, GNSS_FIX,
          HUMIDITY, CURRENT, POWER

        Returns
        -------
        str   CSV line, or
        None  when the simulated mission has ended.
        """
        self.packet_count += 1
        self.synthetic_time += 1.0
        t = self.synthetic_time

        # ----------------------------------------------------------
        # Flight profile — a 65-second nominal mission
        # ----------------------------------------------------------
        state, alt_msl, vert_speed, ground_speed = self._flight_profile(t)

        # Mission end
        if state == STATE_IMPACT and t > 70.0:
            return None

        # ----------------------------------------------------------
        # Relative altitude (above launch pad)
        # ----------------------------------------------------------
        rel_alt = max(0.0, alt_msl - self.launch_alt_msl)

        # ----------------------------------------------------------
        # Apply scenario effects
        # ----------------------------------------------------------
        voltage_base = 8.10
        current_base = 0.42
        sats = 12
        fix = 1
        hdop = 0.9
        hall_rpm = self._nominal_hall_rpm(state, t)

        if self.scenario == "gnss_loss":
            # Drop fix during descent (t = 25..50)
            if 25.0 <= t < 50.0:
                sats = 0
                fix = 0
                hdop = 99.9
            # Recover near the end
            elif t >= 50.0:
                sats = 8
                fix = 1
                hdop = 1.6

        elif self.scenario == "power_fault":
            # Voltage collapses after rocket deploy (t > 18)
            if t > 18.0:
                decay = min(1.0, (t - 18.0) / 20.0)
                voltage_base = 8.10 - decay * 4.5    # down to 3.6 V
                current_base = 0.42 + decay * 0.30

        elif self.scenario == "flywheel_stall":
            # Flywheel stalls during early descent (t = 22..35)
            if 22.0 <= t < 35.0:
                hall_rpm = 0.0

        # (comm_loss handled in _run_loop)

        # Add small measurement noise
        def n(scale):
            return self._rng.gauss(0.0, scale)

        # ----------------------------------------------------------
        # Environment
        # ----------------------------------------------------------
        pressure_pa = 101325.0 * math.exp(-alt_msl / 8434.5) + n(5.0)
        temp_c      = 25.0 - alt_msl * 0.0065 + n(0.05)
        humidity    = 50.0 + 5.0 * math.sin(t * 0.05) + n(0.2)
        lux         = 45000.0 if state not in (STATE_BOOT,) else 200.0
        uv_index    = 0.35 + n(0.02)

        # ----------------------------------------------------------
        # Power
        # ----------------------------------------------------------
        voltage_v = max(0.0, voltage_base + n(0.01))
        current_a = max(0.0, current_base + n(0.005))
        power_w   = voltage_v * current_a

        # ----------------------------------------------------------
        # GNSS — walk the position toward east-north during flight
        # ----------------------------------------------------------
        if ground_speed > 0.01 and state >= STATE_ASCENT:
            # Move ~ground_speed m/s along course = 30°
            dt = 1.0
            course_rad = math.radians(30.0)
            dist_m = ground_speed * dt
            dlat = (dist_m * math.cos(course_rad)) / 111320.0
            dlon = (dist_m * math.sin(course_rad)) / (
                111320.0 * math.cos(math.radians(self._gnss_lat)))
            self._gnss_lat += dlat
            self._gnss_lon += dlon
        self._gnss_alt = alt_msl + n(0.5)

        gnss_time = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        # ----------------------------------------------------------
        # IMU
        # ----------------------------------------------------------
        # Accel — gravity on Z, plus vertical dynamic accel
        ax = 0.10 * math.sin(t * 0.3) + n(0.02)
        ay = 0.08 * math.cos(t * 0.4) + n(0.02)
        az = -9.81 + vert_speed * 0.02 + n(0.05)

        # Gyro — deg/s
        gx = 2.0 * math.sin(t * 0.2) + n(0.1)
        gy = 1.5 * math.cos(t * 0.25) + n(0.1)
        gz = 0.8 * math.sin(t * 0.1) + n(0.1)

        # Magnetometer — µT
        mx = 22.0 + 1.5 * math.sin(t * 0.05) + n(0.1)
        my = -6.0 + 1.0 * math.cos(t * 0.07) + n(0.1)
        mz = 41.0 + 0.8 * math.sin(t * 0.09) + n(0.1)

        # Attitude — smooth sinusoidal + descent wobble
        wobble = 1.0 + (0.5 if state == STATE_DESCENT else 0.0)
        roll_deg  = (wobble * 15.0) * math.sin(t * 0.15) + n(0.3)
        pitch_deg = (wobble * 10.0) * math.cos(t * 0.12) + n(0.3)
        yaw_deg   = ((t * 3.0) % 360.0) + n(0.5)

        # ----------------------------------------------------------
        # Assemble CSV line — EXACT 37-field order
        # ----------------------------------------------------------
        parts = [
            self.team_id,                              # 0  TEAM_ID
            f"{t:.2f}",                                # 1  TIMESTAMP
            str(self.packet_count),                    # 2  PACKET_COUNT
            f"{alt_msl:.2f}",                          # 3  ALTITUDE
            f"{pressure_pa:.1f}",                      # 4  PRESSURE (Pa)
            f"{temp_c:.2f}",                           # 5  TEMP
            f"{voltage_v:.3f}",                        # 6  VOLTAGE
            gnss_time,                                 # 7  GNSS_TIME
            f"{self._gnss_lat:.6f}",                   # 8  GNSS_LATITUDE
            f"{self._gnss_lon:.6f}",                   # 9  GNSS_LONGITUDE
            f"{self._gnss_alt:.2f}",                   # 10 GNSS_ALTITUDE
            str(sats),                                 # 11 GNSS_SATS
            f"{ax:.3f}",                               # 12 ACCEL_X
            f"{ay:.3f}",                               # 13 ACCEL_Y
            f"{az:.3f}",                               # 14 ACCEL_Z
            f"{gx:.3f}",                               # 15 GYRO_X
            f"{gy:.3f}",                               # 16 GYRO_Y
            f"{gz:.3f}",                               # 17 GYRO_Z
            f"{mx:.2f}",                               # 18 MAG_X
            f"{my:.2f}",                               # 19 MAG_Y
            f"{mz:.2f}",                               # 20 MAG_Z
            f"{roll_deg:.2f}",                         # 21 ROLL
            f"{pitch_deg:.2f}",                        # 22 PITCH
            f"{yaw_deg:.2f}",                          # 23 YAW
            f"{lux:.0f}",                              # 24 LIGHT_LUX
            f"{uv_index:.2f}",                         # 25 UV_INDEX
            f"{hall_rpm:.0f}",                         # 26 HALL_RPM
            str(state),                                # 27 FLIGHT_SOFTWARE_STATE
            f"{rel_alt:.2f}",                          # 28 REL_ALTITUDE
            f"{vert_speed:.2f}",                       # 29 VERTICAL_SPEED
            f"{ground_speed:.2f}",                     # 30 GNSS_GROUND_SPEED
            f"{30.0:.1f}",                             # 31 GNSS_COURSE (30°)
            f"{hdop:.2f}",                             # 32 GNSS_HDOP
            str(fix),                                  # 33 GNSS_FIX
            f"{humidity:.1f}",                         # 34 HUMIDITY
            f"{current_a:.2f}",                        # 35 CURRENT
            f"{power_w:.2f}",                          # 36 POWER
        ]
        return ",".join(parts)

    # -----------------------------------------------------------------
    # Flight profile helper
    # -----------------------------------------------------------------
    def _flight_profile(self, t):
        """
        Return (state, altitude_msl, vertical_speed, ground_speed)
        for the elapsed synthetic time `t` in seconds.

        Timeline:
            0-3    BOOT / TEST_MODE / LAUNCH_PAD
            3-15   ASCENT       (rocket motor burn, ~50 m/s²)
           15-18   ROCKET_DEPLOY (apogee ~1000 m)
           18-35   DESCENT      (parachute)
           35-50   AEROBREAK_RELEASE (petal controlled glide)
           50-65   IMPACT (stationary)
        """
        alt_apogee = 1000.0 + self.launch_alt_msl
        a_motor = 50.0                     # m/s²
        t_burn = 15.0 - 3.0                # 12 s motor burn

        if t < 1.0:
            return STATE_BOOT, self.launch_alt_msl, 0.0, 0.0
        if t < 2.0:
            return STATE_TEST_MODE, self.launch_alt_msl, 0.0, 0.0
        if t < 3.0:
            return STATE_LAUNCH_PAD, self.launch_alt_msl, 0.0, 0.0

        if t < 15.0:
            # ASCENT — constant accel from rest
            dt = t - 3.0
            alt = self.launch_alt_msl + 0.5 * a_motor * dt * dt
            vel = a_motor * dt
            gs = 0.5 + dt * 0.05
            return STATE_ASCENT, alt, vel, gs

        if t < 18.0:
            # ROCKET_DEPLOY — coast up to apogee
            dt_burn = t_burn
            alt_burn = self.launch_alt_msl + 0.5 * a_motor * dt_burn * dt_burn
            vel_burn = a_motor * dt_burn        # ~600 m/s
            dt = t - 15.0
            # coasting upward, decelerating at g
            alt = alt_burn + vel_burn * dt - 0.5 * 9.81 * dt * dt
            vel = max(0.0, vel_burn - 9.81 * dt)
            return STATE_ROCKET_DEPLOY, max(alt_apogee, alt), vel, 2.0

        if t < 35.0:
            # DESCENT — parachute, terminal ~15 m/s
            dt = t - 18.0
            alt = max(self.launch_alt_msl + 100.0,
                      alt_apogee - 15.0 * dt)
            return STATE_DESCENT, alt, -15.0, 3.0

        if t < 50.0:
            # AEROBREAK_RELEASE — guided glide, ~2 m/s descent
            dt = t - 35.0
            alt = max(self.launch_alt_msl,
                      self.launch_alt_msl + 100.0 - 2.0 * dt)
            return STATE_AEROBREAK_RELEASE, alt, -2.0, 5.5

        # IMPACT — landed
        return STATE_IMPACT, self.launch_alt_msl, 0.0, 0.0

    # -----------------------------------------------------------------
    # Flywheel RPM profile
    # -----------------------------------------------------------------
    def _nominal_hall_rpm(self, state, t):
        """
        Nominal flywheel spin rate (RPM) across the mission.

        On the pad   : 0  (off)
        During ascent: spin up to ~9000
        Deploy       : peak ~12000
        Descent      : nominal ~9500
        Aerobreak    : spin-down to ~4000
        Impact       : 0
        """
        if state <= STATE_TEST_MODE:
            return 0.0
        if state == STATE_LAUNCH_PAD:
            return 800.0 + self._rng.gauss(0, 20)
        if state == STATE_ASCENT:
            frac = min(1.0, max(0.0, (t - 3.0) / 12.0))
            return 9000.0 * frac + self._rng.gauss(0, 30)
        if state == STATE_ROCKET_DEPLOY:
            return 12000.0 + self._rng.gauss(0, 50)
        if state == STATE_DESCENT:
            return 9500.0 + self._rng.gauss(0, 40)
        if state == STATE_AEROBREAK_RELEASE:
            dt = max(0.0, t - 35.0)
            rpm = max(4000.0, 9500.0 - dt * 350.0)
            return rpm + self._rng.gauss(0, 30)
        # IMPACT
        return 0.0


# -----------------------------------------------------------------
# Convenience: one-shot packet for unit tests
# -----------------------------------------------------------------
def make_test_packet(team_id: str = TEAM_ID) -> str:
    """
    Return a single, valid 37-field CSV line with plausible values.
    Useful for unit tests and for verifying the parser.
    """
    engine = SimulationEngine(packet_callback=lambda _l: None, team_id=team_id)
    # Skip startup states by jumping time forward
    engine.synthetic_time = 25.0
    return engine._generate_synthetic_packet()