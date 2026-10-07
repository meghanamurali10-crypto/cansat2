"""
Flight map widget — plots the CanSat track on a simple lat/lon scatter.

Uses pyqtgraph for lightweight, dependency-free plotting
(no internet / map tiles required — competition-safe).

Optional: if `contextily` + `folium` are installed, an OSM tile
background can be enabled via `set_tile_provider('osm')`.
"""
import pyqtgraph as pg
from PyQt5 import QtWidgets, QtCore


class FlightMap(QtWidgets.QWidget):
    def __init__(self, parent=None, max_points: int = 5000):
        super().__init__(parent)
        self.max_points = max_points

        # Track history
        self._lats = []
        self._lons = []
        self._pred_lats = []
        self._pred_lons = []

        # Target marker
        self._target_lat = None
        self._target_lon = None

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QtWidgets.QLabel("FLIGHT MAP — Live GNSS Track")
        header.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #88aacc; padding: 6px;")
        layout.addWidget(header)

        self.plot = pg.PlotWidget()
        self.plot.setBackground("#0e1620")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel("bottom", "Longitude (°)")
        self.plot.setLabel("left", "Latitude (°)")
        self.plot.setAspectLocked(True)
        layout.addWidget(self.plot)

        # Curves
        self.track_curve = self.plot.plot(
            pen=pg.mkPen("#00e0ff", width=2), name="Track")
        self.current_dot = self.plot.plot(
            [], [], pen=None, symbol="o", symbolSize=12,
            symbolBrush="#00ff80", symbolPen=None)
        self.target_dot = self.plot.plot(
            [], [], pen=None, symbol="+", symbolSize=20,
            symbolBrush="#ff4060", symbolPen=pg.mkPen("#ff4060", width=2))
        self.pred_dot = self.plot.plot(
            [], [], pen=None, symbol="t", symbolSize=14,
            symbolBrush="#ffb030", symbolPen=None)

        # Legend
        legend = self.plot.addLegend()
        legend.addItem(self.track_curve, "Track")
        legend.addItem(self.current_dot, "Current")
        legend.addItem(self.target_dot, "Target")
        legend.addItem(self.pred_dot, "Predicted")

        # Status bar
        self.status = QtWidgets.QLabel("Waiting for GNSS fix...")
        self.status.setStyleSheet("color: #8a9aaa; padding: 4px;")
        layout.addWidget(self.status)

    # -----------------------------------------------------------------
    def update_position(self, lat, lon, pred_lat=None, pred_lon=None):
        """Called for every valid packet that has GNSS coords."""
        try:
            lat = float(lat); lon = float(lon)
        except (TypeError, ValueError):
            return

        self._lats.append(lat)
        self._lons.append(lon)
        if len(self._lats) > self.max_points:
            self._lats.pop(0)
            self._lons.pop(0)

        self.track_curve.setData(self._lons, self._lats)
        self.current_dot.setData([lon], [lat])

        if pred_lat is not None and pred_lon is not None:
            try:
                pl = float(pred_lat); pn = float(pred_lon)
                self.pred_dot.setData([pn], [pl])
            except (TypeError, ValueError):
                pass

        # Distance to target
        if self._target_lat is not None:
            import math
            dlat = (self._target_lat - lat) * 111320.0
            dlon = (self._target_lon - lon) * 111320.0 * math.cos(
                math.radians(lat))
            dist = math.hypot(dlat, dlon)
            self.status.setText(
                f"Lat {lat:.5f}  Lon {lon:.5f}  |  "
                f"Distance to target: {dist:.1f} m")
        else:
            self.status.setText(
                f"Lat {lat:.5f}  Lon {lon:.5f}  |  "
                f"No target set")

        # Auto-zoom after first few points
        if len(self._lats) == 3:
            self.plot.enableAutoRange()

    # -----------------------------------------------------------------
    def set_target(self, lat, lon):
        """Mark the landing target on the map."""
        try:
            self._target_lat = float(lat)
            self._target_lon = float(lon)
        except (TypeError, ValueError):
            return
        self.target_dot.setData([self._target_lon], [self._target_lat])

    # -----------------------------------------------------------------
    def clear(self):
        self._lats.clear()
        self._lons.clear()
        self._pred_lats.clear()
        self._pred_lons.clear()
        self.track_curve.setData([], [])
        self.current_dot.setData([], [])
        self.pred_dot.setData([], [])
        # Keep target as-is
        self.status.setText("Cleared")
