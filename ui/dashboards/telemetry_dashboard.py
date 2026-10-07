"""
Telemetry dashboard — numeric readout of the mandatory mission fields.
"""
from PyQt5 import QtCore, QtWidgets
from ui.dashboards.base_dashboard import BaseDashboard


def _row(grid, r, label):
    l = QtWidgets.QLabel(label); l.setStyleSheet("font-weight: bold;")
    v = QtWidgets.QLabel("--"); v.setAlignment(QtCore.Qt.AlignRight)
    v.setStyleSheet("color: #6bc9ff; font-weight: bold; font-size: 15px;")
    grid.addWidget(l, r, 0); grid.addWidget(v, r, 1)
    return v


class TelemetryDashboard(BaseDashboard):
    def __init__(self, buffer_size: int = 300, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        # ---- Flight ----
        box = QtWidgets.QGroupBox("FLIGHT")
        g = QtWidgets.QGridLayout(box)
        self.val_state       = _row(g, 0,  "Flight State")
        self.val_timestamp   = _row(g, 1,  "Timestamp")
        self.val_packet      = _row(g, 2,  "Packet Count")
        self.val_altitude    = _row(g, 3,  "Altitude (MSL)")
        self.val_rel_alt     = _row(g, 4,  "Relative Altitude")
        self.val_vert_speed  = _row(g, 5,  "Vertical Speed")
        layout.addWidget(box)

        # ---- Environment ----
        env = QtWidgets.QGroupBox("ENVIRONMENT")
        ge = QtWidgets.QGridLayout(env)
        self.val_pressure    = _row(ge, 0, "Pressure")
        self.val_temp        = _row(ge, 1, "Temperature")
        self.val_humidity    = _row(ge, 2, "Humidity")
        self.val_lux         = _row(ge, 3, "Light")
        self.val_uv          = _row(ge, 4, "UV Index")
        layout.addWidget(env)

        # ---- GNSS ----
        nav = QtWidgets.QGroupBox("GNSS")
        gn = QtWidgets.QGridLayout(nav)
        self.val_lat         = _row(gn, 0, "Latitude")
        self.val_lon         = _row(gn, 1, "Longitude")
        self.val_gnss_alt    = _row(gn, 2, "GNSS Altitude")
        self.val_sats        = _row(gn, 3, "Satellites")
        self.val_fix         = _row(gn, 4, "Fix Type")
        self.val_hdop        = _row(gn, 5, "HDOP")
        self.val_gspeed      = _row(gn, 6, "Ground Speed")
        self.val_course      = _row(gn, 7, "Course")
        layout.addWidget(nav)

        # ---- IMU ----
        imu = QtWidgets.QGroupBox("IMU")
        gi = QtWidgets.QGridLayout(imu)
        self.val_ax          = _row(gi, 0, "Accel X")
        self.val_ay          = _row(gi, 1, "Accel Y")
        self.val_az          = _row(gi, 2, "Accel Z")
        self.val_gx          = _row(gi, 3, "Gyro X")
        self.val_gy          = _row(gi, 4, "Gyro Y")
        self.val_gz          = _row(gi, 5, "Gyro Z")
        self.val_mx          = _row(gi, 6, "Mag X")
        self.val_my          = _row(gi, 7, "Mag Y")
        self.val_mz          = _row(gi, 8, "Mag Z")
        self.val_roll        = _row(gi, 9, "Roll")
        self.val_pitch       = _row(gi, 10, "Pitch")
        self.val_yaw         = _row(gi, 11, "Yaw")
        layout.addWidget(imu)

        # ---- Power ----
        pwr = QtWidgets.QGroupBox("POWER")
        gp = QtWidgets.QGridLayout(pwr)
        self.val_voltage     = _row(gp, 0, "Voltage")
        self.val_current     = _row(gp, 1, "Current")
        self.val_power       = _row(gp, 2, "Power")
        self.val_hall        = _row(gp, 3, "Flywheel RPM (N/A)")
        layout.addWidget(pwr)

        layout.addStretch()

    @staticmethod
    def _fmt(v, suffix="", prec=1):
        if v is None:
            return "--"
        try:
            return f"{float(v):.{prec}f}{suffix}"
        except (TypeError, ValueError):
            return "--"

    def update(self, packet):
        # Flight
        self.val_state.setText(str(packet.get("FLIGHT_STATE_NAME")
                                    or packet.get("FLIGHT_SOFTWARE_STATE") or "--"))
        self.val_timestamp.setText(str(packet.get("TIMESTAMP", "--")))
        self.val_packet.setText(str(packet.get("PACKET_COUNT", "--")))
        self.val_altitude.setText(self._fmt(packet.get("ALTITUDE"), " m"))
        self.val_rel_alt.setText(self._fmt(packet.get("REL_ALTITUDE"), " m"))
        self.val_vert_speed.setText(self._fmt(packet.get("VERTICAL_SPEED"), " m/s", 2))

        # Environment
        self.val_pressure.setText(self._fmt(packet.get("PRESSURE"), " Pa", 0))
        self.val_temp.setText(self._fmt(packet.get("TEMP"), " °C"))
        self.val_humidity.setText(self._fmt(packet.get("HUMIDITY"), " %"))
        self.val_lux.setText(self._fmt(packet.get("LIGHT_LUX"), " lux", 0))
        self.val_uv.setText(self._fmt(packet.get("UV_INDEX"), "", 2))

        # GNSS
        self.val_lat.setText(self._fmt(packet.get("GNSS_LATITUDE"), "", 6))
        self.val_lon.setText(self._fmt(packet.get("GNSS_LONGITUDE"), "", 6))
        self.val_gnss_alt.setText(self._fmt(packet.get("GNSS_ALTITUDE"), " m"))
        self.val_sats.setText(str(packet.get("GNSS_SATS", "--")))
        self.val_fix.setText(str(packet.get("GNSS_FIX", "--")))
        self.val_hdop.setText(self._fmt(packet.get("GNSS_HDOP"), "", 2))
        self.val_gspeed.setText(self._fmt(packet.get("GNSS_GROUND_SPEED"), " m/s", 2))
        self.val_course.setText(self._fmt(packet.get("GNSS_COURSE"), "°"))

        # IMU
        self.val_ax.setText(self._fmt(packet.get("ACCEL_X"), " m/s²", 2))
        self.val_ay.setText(self._fmt(packet.get("ACCEL_Y"), " m/s²", 2))
        self.val_az.setText(self._fmt(packet.get("ACCEL_Z"), " m/s²", 2))
        self.val_gx.setText(self._fmt(packet.get("GYRO_X"), " °/s", 2))
        self.val_gy.setText(self._fmt(packet.get("GYRO_Y"), " °/s", 2))
        self.val_gz.setText(self._fmt(packet.get("GYRO_Z"), " °/s", 2))
        self.val_mx.setText(self._fmt(packet.get("MAG_X"), " µT", 1))
        self.val_my.setText(self._fmt(packet.get("MAG_Y"), " µT", 1))
        self.val_mz.setText(self._fmt(packet.get("MAG_Z"), " µT", 1))
        self.val_roll.setText(self._fmt(packet.get("ROLL"), "°"))
        self.val_pitch.setText(self._fmt(packet.get("PITCH"), "°"))
        self.val_yaw.setText(self._fmt(packet.get("YAW"), "°"))

        # Power
        self.val_voltage.setText(self._fmt(packet.get("VOLTAGE"), " V", 2))
        self.val_current.setText(self._fmt(packet.get("CURRENT"), " A", 2))
        self.val_power.setText(self._fmt(packet.get("POWER"), " W", 2))
        self.val_hall.setText(self._fmt(packet.get("HALL_RPM"), " RPM", 0))