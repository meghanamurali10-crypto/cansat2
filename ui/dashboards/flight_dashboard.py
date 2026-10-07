"""
Flight dashboard — attitude & dynamics for the competition display.
"""
from PyQt5 import QtCore, QtWidgets
from ui.dashboards.base_dashboard import BaseDashboard


def _card(title):
    g = QtWidgets.QGroupBox(title)
    v = QtWidgets.QLabel("--")
    v.setAlignment(QtCore.Qt.AlignCenter)
    v.setStyleSheet("color: #6bc9ff; font-weight: bold; font-size: 26px;"
                    "padding: 12px;")
    l = QtWidgets.QVBoxLayout(g)
    l.addWidget(v)
    return g, v


class FlightDashboard(BaseDashboard):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("FLIGHT DASHBOARD | Attitude & Dynamics")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #88aacc;")
        layout.addWidget(title)

        row1 = QtWidgets.QHBoxLayout()
        w1, self.val_roll = _card("ROLL (°)");  row1.addWidget(w1)
        w2, self.val_pitch = _card("PITCH (°)"); row1.addWidget(w2)
        w3, self.val_yaw = _card("YAW (°)");    row1.addWidget(w3)
        layout.addLayout(row1)

        row2 = QtWidgets.QHBoxLayout()
        w4, self.val_gx = _card("GYRO X (°/s)"); row2.addWidget(w4)
        w5, self.val_gy = _card("GYRO Y (°/s)"); row2.addWidget(w5)
        w6, self.val_gz = _card("GYRO Z (°/s)"); row2.addWidget(w6)
        layout.addLayout(row2)

        row3 = QtWidgets.QHBoxLayout()
        w7, self.val_ax = _card("ACCEL X (m/s²)"); row3.addWidget(w7)
        w8, self.val_ay = _card("ACCEL Y (m/s²)"); row3.addWidget(w8)
        w9, self.val_az = _card("ACCEL Z (m/s²)"); row3.addWidget(w9)
        layout.addLayout(row3)

        row4 = QtWidgets.QHBoxLayout()
        w10, self.val_vert = _card("VERT SPEED (m/s)"); row4.addWidget(w10)
        w11, self.val_rel = _card("REL ALT (m)");       row4.addWidget(w11)
        w12, self.val_hall = _card("Flywheel RPM (N/A)");         row4.addWidget(w12)
        layout.addLayout(row4)

        self.state_label = QtWidgets.QLabel("Flight State: --")
        self.state_label.setStyleSheet("font-size: 15px; color: #d0e0f0;"
                                       "padding: 6px; font-weight: bold;")
        layout.addWidget(self.state_label)

        layout.addStretch()

    @staticmethod
    def _fmt(v, prec=2):
        if v is None:
            return "--"
        try:
            return f"{float(v):.{prec}f}"
        except (TypeError, ValueError):
            return "--"

    def update(self, packet):
        self.val_roll.setText(self._fmt(packet.get("ROLL")))
        self.val_pitch.setText(self._fmt(packet.get("PITCH")))
        self.val_yaw.setText(self._fmt(packet.get("YAW")))
        self.val_gx.setText(self._fmt(packet.get("GYRO_X")))
        self.val_gy.setText(self._fmt(packet.get("GYRO_Y")))
        self.val_gz.setText(self._fmt(packet.get("GYRO_Z")))
        self.val_ax.setText(self._fmt(packet.get("ACCEL_X")))
        self.val_ay.setText(self._fmt(packet.get("ACCEL_Y")))
        self.val_az.setText(self._fmt(packet.get("ACCEL_Z")))
        self.val_vert.setText(self._fmt(packet.get("VERTICAL_SPEED")))
        self.val_rel.setText(self._fmt(packet.get("REL_ALTITUDE"), 1))
        self.val_hall.setText(self._fmt(packet.get("HALL_RPM"), 0))
        self.state_label.setText(
            f"Flight State: {packet.get('FLIGHT_STATE_NAME', '--')}")