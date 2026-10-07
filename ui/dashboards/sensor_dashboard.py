"""
Sensor dashboard — environment sensors (pressure, temp, humidity, light, UV).
"""
from PyQt5 import QtWidgets, QtCore
from ui.dashboards.base_dashboard import BaseDashboard


def _row(grid, r, label):
    l = QtWidgets.QLabel(label); l.setStyleSheet("font-weight: bold;")
    v = QtWidgets.QLabel("--"); v.setAlignment(QtCore.Qt.AlignRight)
    v.setStyleSheet("color: #6bc9ff; font-weight: bold; font-size: 16px;")
    grid.addWidget(l, r, 0); grid.addWidget(v, r, 1)
    return v


class SensorDashboard(BaseDashboard):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        box = QtWidgets.QGroupBox("SENSOR SUITE")
        g = QtWidgets.QGridLayout(box)
        self.val_pressure = _row(g, 0, "Pressure")
        self.val_temp     = _row(g, 1, "Temperature")
        self.val_humidity = _row(g, 2, "Humidity")
        self.val_lux      = _row(g, 3, "Light")
        self.val_uv       = _row(g, 4, "UV Index")
        self.val_sats     = _row(g, 5, "GNSS Satellites")
        self.val_fix      = _row(g, 6, "GNSS Fix Type")
        self.val_hdop     = _row(g, 7, "GNSS HDOP")
        layout.addWidget(box)
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
        self.val_pressure.setText(self._fmt(packet.get("PRESSURE"), " Pa", 0))
        self.val_temp.setText(self._fmt(packet.get("TEMP"), " °C"))
        self.val_humidity.setText(self._fmt(packet.get("HUMIDITY"), " %"))
        self.val_lux.setText(self._fmt(packet.get("LIGHT_LUX"), " lux", 0))
        self.val_uv.setText(self._fmt(packet.get("UV_INDEX"), "", 2))
        self.val_sats.setText(str(packet.get("GNSS_SATS", "--")))
        self.val_fix.setText(str(packet.get("GNSS_FIX", "--")))
        self.val_hdop.setText(self._fmt(packet.get("GNSS_HDOP"), "", 2))