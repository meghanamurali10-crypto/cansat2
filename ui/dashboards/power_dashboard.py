"""
Power dashboard — voltage, current, power, flywheel.
"""
from PyQt5 import QtWidgets, QtCore
from ui.dashboards.base_dashboard import BaseDashboard


def _row(grid, r, label):
    l = QtWidgets.QLabel(label); l.setStyleSheet("font-weight: bold;")
    v = QtWidgets.QLabel("--"); v.setAlignment(QtCore.Qt.AlignRight)
    v.setStyleSheet("color: #6bc9ff; font-weight: bold; font-size: 18px;")
    grid.addWidget(l, r, 0); grid.addWidget(v, r, 1)
    return v


class PowerDashboard(BaseDashboard):
    def __init__(self, buffer_size: int = 300, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)

        box = QtWidgets.QGroupBox("POWER SYSTEM")
        g = QtWidgets.QGridLayout(box)
        self.val_voltage = _row(g, 0, "Battery Voltage")
        self.val_current = _row(g, 1, "Current Draw")
        self.val_power   = _row(g, 2, "Instantaneous Power")
        self.val_hall    = _row(g, 3, "Flywheel RPM")
        layout.addWidget(box)
        layout.addStretch()

    @staticmethod
    def _fmt(v, suffix="", prec=2):
        if v is None:
            return "--"
        try:
            return f"{float(v):.{prec}f}{suffix}"
        except (TypeError, ValueError):
            return "--"

    def update(self, packet):
        self.val_voltage.setText(self._fmt(packet.get("VOLTAGE"), " V"))
        self.val_current.setText(self._fmt(packet.get("CURRENT"), " A"))
        self.val_power.setText(self._fmt(packet.get("POWER"), " W"))
        self.val_hall.setText(self._fmt(packet.get("HALL_RPM"), " RPM", 0))