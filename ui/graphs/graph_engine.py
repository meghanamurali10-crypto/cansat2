"""
Graph engine — live plots for the mandatory fields + flywheel.
"""
import pyqtgraph as pg
from PyQt5 import QtWidgets


class GraphEngine(QtWidgets.QWidget):
    def __init__(self, buffer_size: int = 300, parent=None):
        super().__init__(parent)
        self.buffer_size = buffer_size
        self._buffers = {}

        layout = QtWidgets.QVBoxLayout(self)
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        self._plots = {}
        for key, (title, ylabel, color) in {
            "altitude":  ("Altitude (m)",       "m",   "y"),
            "rel_alt":   ("Relative Altitude",  "m",   "c"),
            "pressure":  ("Pressure (Pa)",      "Pa",  "m"),
            "temp":      ("Temperature (°C)",   "°C",  "r"),
            "volt":      ("Voltage (V)",        "V",   "g"),
            "gspeed":    ("GNSS Ground Speed",  "m/s", "w"),
            "rpm":       ("Flywheel Spin Rate", "RPM", "#ff66cc"),
            "roll":      ("Roll / Pitch / Yaw", "°",   "y"),
        }.items():
            plot = pg.PlotWidget(title=title)
            plot.setLabel("left", ylabel)
            plot.setLabel("bottom", "Sample")
            plot.showGrid(x=True, y=True, alpha=0.3)
            curve = plot.plot(pen=pg.mkPen(color, width=2))
            self._plots[key] = (plot, curve)
            self._buffers[key] = []
            self.tabs.addTab(plot, title.split(" ")[0])

    def _push(self, key, value):
        buf = self._buffers[key]
        buf.append(value)
        if len(buf) > self.buffer_size:
            buf.pop(0)
        self._plots[key][1].setData(buf)

    def update(self, packet):
        def v(name, default=0.0):
            x = packet.get(name)
            try:
                return float(x) if x is not None else default
            except (TypeError, ValueError):
                return default

        self._push("altitude", v("ALTITUDE"))
        self._push("rel_alt", v("REL_ALTITUDE"))
        self._push("pressure", v("PRESSURE"))
        self._push("temp", v("TEMP"))
        self._push("volt", v("VOLTAGE"))
        self._push("gspeed", v("GNSS_GROUND_SPEED"))
        self._push("rpm", v("HALL_RPM"))
        self._push("roll", v("ROLL"))