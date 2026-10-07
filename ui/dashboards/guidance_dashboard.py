"""
Guidance dashboard — READ-ONLY display of CanSat's onboard decisions.
GS does not compute or transmit glide commands.
"""
from PyQt5 import QtCore, QtWidgets

from ui.dashboards.base_dashboard import BaseDashboard


def _row(grid, r, label):
    l = QtWidgets.QLabel(label)
    l.setStyleSheet("font-weight: bold;")
    v = QtWidgets.QLabel("--")
    v.setAlignment(QtCore.Qt.AlignRight)
    v.setStyleSheet("color: #6bc9ff; font-weight: bold; font-size: 15px;")
    grid.addWidget(l, r, 0)
    grid.addWidget(v, r, 1)
    return v


class GuidanceDashboard(BaseDashboard):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        # ----------------- Precision landing -----------------
        box = QtWidgets.QGroupBox("PRECISION LANDING")
        grid = QtWidgets.QGridLayout(box)
        self.val_altitude      = _row(grid, 0,  "Altitude (MSL)")
        self.val_rel_alt       = _row(grid, 1,  "Relative Altitude")
        self.val_vert_speed    = _row(grid, 2,  "Vertical Speed")
        self.val_pred_lat      = _row(grid, 3,  "Predicted Lat")
        self.val_pred_lon      = _row(grid, 4,  "Predicted Lon")
        self.val_pred_err      = _row(grid, 5,  "Predicted Error")
        self.val_err_north     = _row(grid, 6,  "Error North")
        self.val_err_east      = _row(grid, 7,  "Error East")
        self.val_xtrack        = _row(grid, 8,  "Cross Track Error")
        self.val_petal         = _row(grid, 9,  "Petal State")
        self.val_glide         = _row(grid, 10, "Glide Command")
        self.val_dwell         = _row(grid, 11, "Dwell Time")
        self.val_state         = _row(grid, 12, "Flight State")
        layout.addWidget(box)

        # ----------------- Attitude -----------------
        att = QtWidgets.QGroupBox("ATTITUDE")
        ag = QtWidgets.QGridLayout(att)
        self.val_roll          = _row(ag, 0, "Roll")
        self.val_pitch         = _row(ag, 1, "Pitch")
        self.val_yaw           = _row(ag, 2, "Yaw")
        self.val_gyro_x        = _row(ag, 3, "Gyro X")
        self.val_gyro_y        = _row(ag, 4, "Gyro Y")
        self.val_gyro_z        = _row(ag, 5, "Gyro Z")
        layout.addWidget(att)

        # ----------------- Navigation -----------------
        nav = QtWidgets.QGroupBox("NAVIGATION")
        ng = QtWidgets.QGridLayout(nav)
        self.val_gnss_lat      = _row(ng, 0, "GNSS Latitude")
        self.val_gnss_lon      = _row(ng, 1, "GNSS Longitude")
        self.val_gnss_alt      = _row(ng, 2, "GNSS Altitude")
        self.val_gnss_sats     = _row(ng, 3, "GNSS Satellites")
        self.val_gnss_fix      = _row(ng, 4, "GNSS Fix")
        self.val_gnss_hdop     = _row(ng, 5, "GNSS HDOP")
        self.val_gnss_gspeed   = _row(ng, 6, "GNSS Ground Speed")
        self.val_gnss_course   = _row(ng, 7, "GNSS Course")
        layout.addWidget(nav)

        # ----------------- Wind -----------------
        wind = QtWidgets.QGroupBox("WIND")
        wg = QtWidgets.QGridLayout(wind)
        self.val_wind_speed    = _row(wg, 0, "Wind Speed")
        self.val_wind_dir      = _row(wg, 1, "Wind Direction")
        self.val_distance      = _row(wg, 2, "Distance to Target")
        layout.addWidget(wind)

        # ----------------- Target entry -----------------
        tgt = QtWidgets.QGroupBox("LANDING TARGET")
        tg = QtWidgets.QGridLayout(tgt)
        tg.addWidget(QtWidgets.QLabel("Latitude"), 0, 0)
        self.target_lat_input = QtWidgets.QLineEdit()
        tg.addWidget(self.target_lat_input, 0, 1)
        tg.addWidget(QtWidgets.QLabel("Longitude"), 1, 0)
        self.target_lon_input = QtWidgets.QLineEdit()
        tg.addWidget(self.target_lon_input, 1, 1)
        self.set_target_btn = QtWidgets.QPushButton("SET TARGET")
        tg.addWidget(self.set_target_btn, 2, 0, 1, 2)
        layout.addWidget(tgt)

        # ----------------- Uplink commands -----------------
        cmd = QtWidgets.QGroupBox("TEST / UPLINK COMMANDS")
        cg = QtWidgets.QGridLayout(cmd)
        self.sim_enable_btn  = QtWidgets.QPushButton("SIM ENABLE")
        self.sim_disable_btn = QtWidgets.QPushButton("SIM DISABLE")
        self.deploy_now_btn  = QtWidgets.QPushButton("DEPLOY NOW")
        self.ping_btn        = QtWidgets.QPushButton("PING")
        cg.addWidget(self.sim_enable_btn,  0, 0)
        cg.addWidget(self.sim_disable_btn, 0, 1)
        cg.addWidget(self.deploy_now_btn,  1, 0)
        cg.addWidget(self.ping_btn,        1, 1)
        layout.addWidget(cmd)

        layout.addStretch()

    @staticmethod
    def _describe_petal(v):
        try:
            return {0: "NEUTRAL", 1: "PETAL 1", 2: "PETAL 2", 3: "PETAL 3"}.get(
                int(v), f"UNK({v})")
        except (TypeError, ValueError):
            return str(v)

    @staticmethod
    def _fmt(v, suffix="", prec=1):
        if v is None:
            return "--"
        try:
            return f"{float(v):.{prec}f}{suffix}"
        except (TypeError, ValueError):
            return "--"

    def update(self, packet):
        # Precision landing
        self.val_altitude.setText(self._fmt(packet.get("ALTITUDE"), " m"))
        self.val_rel_alt.setText(self._fmt(packet.get("REL_ALTITUDE"), " m"))
        self.val_vert_speed.setText(self._fmt(packet.get("VERTICAL_SPEED"), " m/s", 2))
        self.val_pred_lat.setText(self._fmt(packet.get("PRED_LAT"), "", 6))
        self.val_pred_lon.setText(self._fmt(packet.get("PRED_LON"), "", 6))
        en = packet.get("ERROR_NORTH")
        ee = packet.get("ERROR_EAST")
        try:
            err = (float(en) ** 2 + float(ee) ** 2) ** 0.5
            self.val_pred_err.setText(f"{err:.1f} m")
        except (TypeError, ValueError):
            self.val_pred_err.setText("--")
        self.val_err_north.setText(self._fmt(en, " m"))
        self.val_err_east.setText(self._fmt(ee, " m"))
        self.val_xtrack.setText(self._fmt(packet.get("CROSS_ERROR"), " m"))
        self.val_petal.setText(self._describe_petal(packet.get("PETAL_STATE")))
        self.val_glide.setText(str(packet.get("GLIDE_CMD") or "--"))
        self.val_dwell.setText(self._fmt(packet.get("DWELL_MS"), " ms", 0))
        self.val_state.setText(str(packet.get("FLIGHT_STATE_NAME")
                                    or packet.get("FLIGHT_SOFTWARE_STATE") or "--"))

        # Attitude
        self.val_roll.setText(self._fmt(packet.get("ROLL"), "°"))
        self.val_pitch.setText(self._fmt(packet.get("PITCH"), "°"))
        self.val_yaw.setText(self._fmt(packet.get("YAW"), "°"))
        self.val_gyro_x.setText(self._fmt(packet.get("GYRO_X"), " °/s"))
        self.val_gyro_y.setText(self._fmt(packet.get("GYRO_Y"), " °/s"))
        self.val_gyro_z.setText(self._fmt(packet.get("GYRO_Z"), " °/s"))

        # Navigation
        self.val_gnss_lat.setText(self._fmt(packet.get("GNSS_LATITUDE"), "", 6))
        self.val_gnss_lon.setText(self._fmt(packet.get("GNSS_LONGITUDE"), "", 6))
        self.val_gnss_alt.setText(self._fmt(packet.get("GNSS_ALTITUDE"), " m"))
        self.val_gnss_sats.setText(str(packet.get("GNSS_SATS", "--")))
        self.val_gnss_fix.setText(str(packet.get("GNSS_FIX", "--")))
        self.val_gnss_hdop.setText(self._fmt(packet.get("GNSS_HDOP"), "", 2))
        self.val_gnss_gspeed.setText(self._fmt(packet.get("GNSS_GROUND_SPEED"), " m/s", 2))
        self.val_gnss_course.setText(self._fmt(packet.get("GNSS_COURSE"), "°"))

        # Distance to target
        tlat = getattr(self, "_target_lat", None)
        tlon = getattr(self, "_target_lon", None)
        clat = packet.get("GNSS_LATITUDE")
        clon = packet.get("GNSS_LONGITUDE")
        if None not in (tlat, tlon, clat, clon):
            try:
                import math
                dlat = (float(tlat) - float(clat)) * 111320.0
                dlon = (float(tlon) - float(clon)) * 111320.0 * \
                       math.cos(math.radians(float(clat)))
                d = math.hypot(dlat, dlon)
                self.val_distance.setText(f"{d:.1f} m")
            except (TypeError, ValueError):
                self.val_distance.setText("--")

    def update_wind(self, speed_mps, direction_deg):
        try:
            self.val_wind_speed.setText(f"{float(speed_mps):.1f} m/s")
            self.val_wind_dir.setText(f"{float(direction_deg):.0f}°")
        except (TypeError, ValueError):
            pass

    def set_target_marker(self, lat, lon):
        self._target_lat = lat
        self._target_lon = lon

    def show_command_status(self, text):
        pass
