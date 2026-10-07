"""
Telemetry constants — 37-field format.

Field order (comma-separated, ASCII, ending with \\n):
TEAM_ID,TIMESTAMP,PACKET_COUNT,ALTITUDE,PRESSURE,TEMP,VOLTAGE,
GNSS_TIME,GNSS_LATITUDE,GNSS_LONGITUDE,GNSS_ALTITUDE,GNSS_SATS,
ACCEL_X,ACCEL_Y,ACCEL_Z,GYRO_X,GYRO_Y,GYRO_Z,
MAG_X,MAG_Y,MAG_Z,ROLL,PITCH,YAW,
LIGHT_LUX,UV_INDEX,HALL_RPM,FLIGHT_SOFTWARE_STATE,
REL_ALTITUDE,VERTICAL_SPEED,GNSS_GROUND_SPEED,GNSS_COURSE,
GNSS_HDOP,GNSS_FIX,HUMIDITY,CURRENT,POWER
"""

# ---------------------------------------------------------------
# Team ID — must match firmware exactly.
# Full format per IN-SPACe guidelines: 2026-IN-SPACECAN-7USAT-XXX
# ---------------------------------------------------------------
TEAM_ID = "CANSAT01"   # change 1234 to your number

# ---------------------------------------------------------------
# RF Telecommands
# ---------------------------------------------------------------
CMD_TELEMETRY_ON   = "TXON"
CMD_TELEMETRY_OFF  = "TXOFF"
CMD_CALIBRATE      = "CAL"
CMD_RESET_GPS      = "GPSRST"
CMD_BEACON_ON      = "BCON"
CMD_BEACON_OFF     = "BCOFF"
CMD_LOG_START      = "LOGSTART"
CMD_LOG_STOP       = "LOGSTOP"
CMD_RESET_TIME     = "TIMERST"
CMD_DEPLOY_NOW     = "DEPLOY"
CMD_SET_TARGET     = "SET_TARGET"
CMD_SIM_ENABLE     = "SIM_ENABLE"
CMD_SIM_DISABLE    = "SIM_DISABLE"
CMD_PING           = "PING"

# ---------------------------------------------------------------
# Field names — EXACT order matters. Index 0 = TEAM_ID.
# ---------------------------------------------------------------
FIELD_NAMES = [
    "TEAM_ID",                #  0  string
    "TIMESTAMP",              #  1  float (seconds since boot)
    "PACKET_COUNT",           #  2  int
    "ALTITUDE",               #  3  float (m, MSL)
    "PRESSURE",               #  4  float (hPa raw -> converted to Pa)
    "TEMP",                   #  5  float (°C)
    "VOLTAGE",                #  6  float (V)
    "GNSS_TIME",              #  7  string
    "GNSS_LATITUDE",          #  8  float (deg)
    "GNSS_LONGITUDE",         #  9  float (deg)
    "GNSS_ALTITUDE",          # 10  float (m)
    "GNSS_SATS",              # 11  int
    "ACCEL_X",                # 12  float (m/s²)
    "ACCEL_Y",                # 13  float (m/s²)
    "ACCEL_Z",                # 14  float (m/s²)
    "GYRO_X",                 # 15  float (deg/s)
    "GYRO_Y",                 # 16  float (deg/s)
    "GYRO_Z",                 # 17  float (deg/s)
    "MAG_X",                  # 18  float (µT)
    "MAG_Y",                  # 19  float (µT)
    "MAG_Z",                  # 20  float (µT)
    "ROLL",                   # 21  float (deg)
    "PITCH",                  # 22  float (deg)
    "YAW",                    # 23  float (deg)
    "LIGHT_LUX",              # 24  float (lux)
    "UV_INDEX",               # 25  float
    "HALL_RPM",               # 26  float (RPM)  ← flywheel spin rate
    "FLIGHT_SOFTWARE_STATE",  # 27  int
    "REL_ALTITUDE",           # 28  float (m, above launch)
    "VERTICAL_SPEED",         # 29  float (m/s)
    "GNSS_GROUND_SPEED",      # 30  float (m/s)
    "GNSS_COURSE",            # 31  float (deg)
    "GNSS_HDOP",              # 32  float
    "GNSS_FIX",               # 33  int (0=no fix, 1=GPS, 2=DGPS, ...)
    "HUMIDITY",               # 34  float (%)
    "CURRENT",                # 35  float (A)
    "POWER",                  # 36  float (W)
]

# ---------------------------------------------------------------
# Field type sets
# ---------------------------------------------------------------
FLOAT_FIELDS = {
    "TIMESTAMP",
    "ALTITUDE", "PRESSURE", "TEMP", "VOLTAGE",
    "GNSS_LATITUDE", "GNSS_LONGITUDE", "GNSS_ALTITUDE",
    "ACCEL_X", "ACCEL_Y", "ACCEL_Z",
    "GYRO_X", "GYRO_Y", "GYRO_Z",
    "MAG_X", "MAG_Y", "MAG_Z",
    "ROLL", "PITCH", "YAW",
    "LIGHT_LUX", "UV_INDEX", "HALL_RPM",
    "REL_ALTITUDE", "VERTICAL_SPEED",
    "GNSS_GROUND_SPEED", "GNSS_COURSE", "GNSS_HDOP",
    "HUMIDITY", "CURRENT", "POWER",
}

INT_FIELDS = {
    "PACKET_COUNT", "GNSS_SATS",
    "FLIGHT_SOFTWARE_STATE", "GNSS_FIX",
}

# ---------------------------------------------------------------
# No triplet fields — accelerometer and gyro are separate columns now
# ---------------------------------------------------------------
TRIPLET_FIELDS = set()

# ---------------------------------------------------------------
# Legacy aliases (old name in old code -> new name)
# ---------------------------------------------------------------
FIELD_ALIASES = {
    "FLIGHT_STATE": "FLIGHT_SOFTWARE_STATE",
    "TIME_STAMPING": "TIMESTAMP",
    "HUM": "HUMIDITY",
    "LUX": "LIGHT_LUX",
    "UV": "UV_INDEX",
}

# ---------------------------------------------------------------
# Flight states — per IN-SPACe CAN-7USAT 2026 guidelines section 6.2
# ---------------------------------------------------------------
FLIGHT_STATES = {
    0: "BOOT",
    1: "TEST_MODE",
    2: "LAUNCH_PAD",
    3: "ASCENT",
    4: "ROCKET_DEPLOY",
    5: "DESCENT",
    6: "AEROBREAK_RELEASE",
    7: "IMPACT",
}

# ---------------------------------------------------------------
# Unit conversion helpers
# ---------------------------------------------------------------
def pressure_to_pa(raw, unit: str = "hPa"):
    """Convert pressure to Pascals (SI units per guidelines)."""
    if raw is None:
        return None
    try:
        raw = float(raw)
    except (TypeError, ValueError):
        return None
    if unit == "hPa":
        return raw * 100.0
    if unit == "kPa":
        return raw * 1000.0
    return raw