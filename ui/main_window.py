"""
Main window — CAN-7USAT Ground Station.
Routes packets, updates dashboards, handles uplink commands, live map.

Removed: Camera dashboard, Flywheel/HALL monitor.
"""
import os
import re
import time

from PyQt5 import QtWidgets, QtCore

from config.config_loader import Config
from core.telemetry.constants import (
    TEAM_ID, CMD_TELEMETRY_ON, CMD_TELEMETRY_OFF, CMD_CALIBRATE,
    CMD_RESET_GPS, CMD_LOG_START, CMD_LOG_STOP, CMD_DEPLOY_NOW,
    CMD_SIM_ENABLE, CMD_SIM_DISABLE, CMD_PING,
)
from core.telemetry.packet import (
    parse_packet, add_legacy_aliases, PacketParseError,
)
from core.telemetry.packet_sequencer import PacketSequencer
from core.data.csv_logger import CSVLogger
from core.hardware.serial_link import SerialLink, list_available_ports, guess_gs_port
from core.comms.uplink import build as build_uplink
from core.comms.command_tracker import CommandTracker

from core.ai.fingerprint import EnvironmentalFingerprintEngine
from core.ai.trend_predictor import AtmosphericTrendPredictor
from core.ai.wind_drift import StabilityMonitor, WindEstimator, estimate_landing_drift
from core.ai.recovery_health import RecoveryHealthMonitor
from core.ai.fault_detection import FaultDetector

from guidance.wind_estimator import WindEstimator as GuidanceWindEstimator

from ui.dashboards import (
    TelemetryDashboard, PowerDashboard, RecoveryDashboard,
    FlightDashboard, SensorDashboard, MissionDashboard, GuidanceDashboard,
)
from ui.graphs import GraphEngine
from ui.commands import CommandPanel
from ui.simulation_tab import SimulationTab
from ui.reports import ReportGenerator
from ui.widgets import FlightMap

from utils.logger import get_logger

logger = get_logger(__name__)


STYLESHEET = """
QMainWindow { background-color: #1e2a38; }
QTabWidget::pane { border: 1px solid #2a3a4a; background: #141c26; }
QTabBar::tab {
    background: #2a3a4a; color: #8a9aaa; padding: 8px 18px;
    margin-right: 4px; border-top-left-radius: 6px;
    border-top-right-radius: 6px; font-weight: bold; font-size: 13px;
}
QTabBar::tab:selected { background: #3a6a8a; color: #ffffff; }
QGroupBox {
    border: 1px solid #2a3a4a; border-radius: 8px; margin-top: 14px;
    padding-top: 12px; background: #1a2632; color: #c0d0e0; font-size: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 10px;
    color: #6a9ac0; font-weight: bold; font-size: 15px;
}
QLabel { color: #d0dce8; font-size: 13px; }
QPushButton {
    background: #2a4a6a; color: #d0e0f0; border: 1px solid #3a5a7a;
    border-radius: 6px; padding: 8px 16px; font-weight: bold; font-size: 13px;
}
QPushButton:hover { background: #3a6a8a; border: 1px solid #5a8aaa; }
QComboBox {
    background: #1a2632; color: #c0d0e0; border: 1px solid #2a4a5a;
    border-radius: 4px; padding: 6px 12px; font-size: 13px;
}
"""


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, cfg: Config = None):
        super().__init__()
        self.cfg = cfg or Config()
        self.setWindowTitle(f"CAN-7USAT Ground Station — {TEAM_ID}")
        self.resize(1600, 1000)
        self.setMinimumSize(1400, 900)
        self.setStyleSheet(STYLESHEET)

        self.buffer_size = self.cfg.get("mission.graph_buffer_size", 300)
        self.pressure_unit = self.cfg.get("units.pressure_raw", "hPa")

        # Backend
        self.serial_link = None
        self.csv_logger = CSVLogger()
        self.sequencer = PacketSequencer()
        self.fp_engine = EnvironmentalFingerprintEngine()
        self.trend_predictor = AtmosphericTrendPredictor()
        self.stability_monitor = StabilityMonitor()
        self.wind_estimator = WindEstimator()
        self.recovery_health = RecoveryHealthMonitor()
        self.fault_detector = FaultDetector()
        self.command_tracker = CommandTracker(timeout_s=5.0)

        # Guidance (read-only)
        self.guidance_wind_estimator = None
        self._guidance_reference_set = False
        self._target_lat = None
        self._target_lon = None

        # Link health
        self._last_packet_monotonic = 0.0
        self._packet_times = []
        self._rejected_count = 0
        self._last_rssi = None

        # AI data holder for report
        self._ai_data = {}

        # Build UI
        self._build_ui()
        self._wire_guidance_ui()

        # Timers
        self.poll_timer = QtCore.QTimer()
        self.poll_timer.timeout.connect(self._poll_serial)
        self.poll_timer.start(100)

        self.health_timer = QtCore.QTimer()
        self.health_timer.timeout.connect(self._update_link_health)
        self.health_timer.start(500)

        logger.info("MainWindow initialized")

    # ---------------- UI ----------------
    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Top bar
        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(10)
        self.port_combo = QtWidgets.QComboBox()
        self._refresh_ports()
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_ports)
        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.connect_btn.clicked.connect(self._toggle_connect)
        start_btn = QtWidgets.QPushButton("Start Telemetry")
        start_btn.clicked.connect(lambda: self._send_cmd(CMD_TELEMETRY_ON))
        stop_btn = QtWidgets.QPushButton("Stop Telemetry")
        stop_btn.clicked.connect(lambda: self._send_cmd(CMD_TELEMETRY_OFF))
        calib_btn = QtWidgets.QPushButton("Calibrate")
        calib_btn.setStyleSheet("background: #6a4a2a; border: 1px solid #8a6a3a;")
        calib_btn.clicked.connect(self._on_calibrate)

        self.link_led = QtWidgets.QLabel("●")
        self.link_led.setStyleSheet("color: #e06050; font-size: 20px;")
        self.link_rate_label = QtWidgets.QLabel("0.0 Hz")
        self.rssi_label = QtWidgets.QLabel("RSSI: --")
        self.rssi_label.setStyleSheet("color: #8a9aaa; font-weight: bold;")
        self.status_label = QtWidgets.QLabel("STATUS: DISCONNECTED")
        self.status_label.setStyleSheet("color: #e06050; font-weight: bold;")

        bar.addWidget(QtWidgets.QLabel("Port:"))
        bar.addWidget(self.port_combo)
        bar.addWidget(refresh_btn)
        bar.addWidget(self.connect_btn)
        bar.addWidget(start_btn)
        bar.addWidget(stop_btn)
        bar.addWidget(calib_btn)
        bar.addStretch()
        bar.addWidget(self.link_led)
        bar.addWidget(self.link_rate_label)
        bar.addWidget(self.rssi_label)
        bar.addWidget(self.status_label)
        main_layout.addLayout(bar)

        # Tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setUsesScrollButtons(True)

        def wrap(w):
            s = QtWidgets.QScrollArea()
            s.setWidgetResizable(True)
            s.setWidget(w)
            s.setStyleSheet("background: #141c26;")
            return s

        self.mission_dashboard   = MissionDashboard()
        self.telemetry_dashboard = TelemetryDashboard(buffer_size=self.buffer_size)
        self.power_dashboard     = PowerDashboard(buffer_size=self.buffer_size)
        self.recovery_dashboard  = RecoveryDashboard()
        self.flight_dashboard    = FlightDashboard()
        self.sensor_dashboard    = SensorDashboard()
        self.graph_engine        = GraphEngine(buffer_size=self.buffer_size)
        self.guidance_dashboard  = GuidanceDashboard()
        self.command_panel       = CommandPanel(send_command_callback=self._send_cmd)
        self.simulation_tab      = SimulationTab(packet_callback=self._inject_packet)
        self.flight_map          = FlightMap()

        self.tabs.addTab(wrap(self.mission_dashboard),   "Mission")
        self.tabs.addTab(wrap(self.telemetry_dashboard), "Telemetry")
        self.tabs.addTab(wrap(self.power_dashboard),     "Power")
        self.tabs.addTab(wrap(self.recovery_dashboard),  "Recovery")
        self.tabs.addTab(wrap(self.flight_dashboard),    "Flight")
        self.tabs.addTab(wrap(self.sensor_dashboard),    "Sensors")
        self.tabs.addTab(wrap(self.graph_engine),        "Graphs")
        self.tabs.addTab(wrap(self.guidance_dashboard),  "Guidance")
        self.tabs.addTab(self.flight_map,                "Map")
        self.tabs.addTab(wrap(self.command_panel),       "Commands")
        self.tabs.addTab(wrap(self.simulation_tab),      "Simulation")

        # Reports
        rt = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(rt)
        rl.addWidget(QtWidgets.QLabel("Generate Mission Report"))
        self.report_btn = QtWidgets.QPushButton("Generate PDF Report")
        self.report_btn.clicked.connect(self._generate_report)
        rl.addWidget(self.report_btn)
        self.report_status = QtWidgets.QLabel("Ready")
        rl.addWidget(self.report_status)
        rl.addStretch()
        self.tabs.addTab(rt, "Reports")

        main_layout.addWidget(self.tabs)

        self.bottom_status = QtWidgets.QLabel("System Initialized")
        self.bottom_status.setStyleSheet("color: #6a8aaa; padding: 4px;")
        main_layout.addWidget(self.bottom_status)

    def _wire_guidance_ui(self):
        g = self.guidance_dashboard
        g.set_target_btn.clicked.connect(self._on_send_target)
        g.sim_enable_btn.clicked.connect(lambda: self._send_cmd(CMD_SIM_ENABLE))
        g.sim_disable_btn.clicked.connect(lambda: self._send_cmd(CMD_SIM_DISABLE))
        g.deploy_now_btn.clicked.connect(lambda: self._send_cmd(CMD_DEPLOY_NOW))
        g.ping_btn.clicked.connect(lambda: self._send_cmd(CMD_PING))

    # ---------------- Target ----------------
    def _on_send_target(self):
        try:
            lat = float(self.guidance_dashboard.target_lat_input.text())
            lon = float(self.guidance_dashboard.target_lon_input.text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Invalid target",
                                          "Enter decimal latitude and longitude.")
            return
        cmd = build_uplink("SET_TARGET", lat, lon)
        try:
            seq = int(cmd.split(",")[1])
            self.command_tracker.sent(seq, "SET_TARGET")
        except (ValueError, IndexError):
            pass
        self._send_cmd(cmd, raw=True)
        self._target_lat, self._target_lon = lat, lon
        try:
            self.guidance_dashboard.set_target_marker(lat, lon)
        except Exception:
            pass
        try:
            self.flight_map.set_target(lat, lon)
        except Exception:
            pass
        self.bottom_status.setText(f"Target sent: {lat:.5f}, {lon:.5f}")

    # ---------------- Serial ----------------
    def _refresh_ports(self):
        self.port_combo.clear()
        for dev, desc in list_available_ports():
            self.port_combo.addItem(f"{dev} ({desc})", userData=dev)
        guess = guess_gs_port()
        if guess:
            for i in range(self.port_combo.count()):
                if self.port_combo.itemData(i) == guess:
                    self.port_combo.setCurrentIndex(i)
                    break
        if self.port_combo.count() == 0:
            self.port_combo.addItem("No ports")

    def _toggle_connect(self):
        if self.serial_link is None:
            dev = self.port_combo.currentData()
            if not dev:
                QtWidgets.QMessageBox.warning(self, "No port", "Select a port.")
                return
            try:
                self.serial_link = SerialLink(dev)
                self.serial_link.connect()
                self.connect_btn.setText("Disconnect")
                self.status_label.setText("STATUS: CONNECTED")
                self.status_label.setStyleSheet("color: #60c090; font-weight: bold;")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
                self.serial_link = None
        else:
            self.serial_link.disconnect()
            self.serial_link = None
            self.connect_btn.setText("Connect")
            self.status_label.setText("STATUS: DISCONNECTED")
            self.status_label.setStyleSheet("color: #e06050; font-weight: bold;")

    def _poll_serial(self):
        if not self.serial_link or not self.serial_link.is_connected():
            return
        for line in self.serial_link.read_available_lines():
            self._handle_line(line)

    # ---------------- Packet handling ----------------
    def _handle_line(self, line):
        if line.startswith("CMD_ECHO"):
            self._on_cmd_echo(line)
            return
        if line.startswith("CALIBRATION_COMPLETE"):
            self._on_calibration_complete(line)
            return
        if line.startswith("CALIBRATION_FAILED"):
            self._on_calibration_failed(line)
            return

        m = re.search(r"RSSI:(-?\d+)", line)
        if m:
            self._last_rssi = int(m.group(1))
            color = ("#00C853" if self._last_rssi > -90
                     else "#FFB300" if self._last_rssi > -110
                     else "#D50000")
            self.rssi_label.setText(f"RSSI: {self._last_rssi} dBm")
            self.rssi_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        try:
            packet = add_legacy_aliases(parse_packet(line, self.pressure_unit))
        except PacketParseError as e:
            self._rejected_count += 1
            self.bottom_status.setText(f"Rejected #{self._rejected_count}: {e}")
            return

        self._last_packet_monotonic = time.monotonic()
        self.csv_logger.log(packet)

        for dash in (self.mission_dashboard, self.telemetry_dashboard,
                     self.power_dashboard, self.recovery_dashboard,
                     self.flight_dashboard, self.sensor_dashboard):
            try:
                dash.update(packet)
            except Exception as e:
                logger.debug(f"Dashboard update error: {e}")

        try:
            self.graph_engine.update(packet)
        except Exception as e:
            logger.debug(f"Graph update error: {e}")

        self._update_ai(packet)
        self._update_guidance(packet)
        self._update_map(packet)

        self.bottom_status.setText(
            f"Packet #{packet.get('PACKET_COUNT', '?')} | "
            f"State {packet.get('FLIGHT_STATE_NAME', '?')} | "
            f"Rejected {self._rejected_count}")

    def _inject_packet(self, raw_line):
        self._handle_line(raw_line)

    # ---------------- AI ----------------
    def _update_ai(self, packet):
        try:
            fp = self.fp_engine.update(packet)
            fingerprint = fp.get("class_label", "--")
        except Exception:
            fingerprint = "--"

        wind_str = "Wind: --"
        landing_str = "Landing: --"
        wind_data = {}
        state_name = packet.get("FLIGHT_STATE_NAME", "")

        if state_name in ("DESCENT", "AEROBREAK_RELEASE"):
            try:
                wind = self.wind_estimator.update(packet)
                if wind.get("available"):
                    wind_str = (f"{wind['wind_speed_mps']:.1f} m/s @ "
                                f"{wind['wind_direction_deg']:.0f}°")
                    wind_data = wind
                    drift = estimate_landing_drift(
                        packet.get("GNSS_LATITUDE"), packet.get("GNSS_LONGITUDE"),
                        packet.get("ALTITUDE"), 3.0,
                        wind["wind_speed_mps"], wind["wind_direction_deg"])
                    if drift.get("available"):
                        t = drift["time_to_land_seconds"]
                        landing_str = f"~{int(t//60)}m {int(t%60)}s"
            except Exception:
                pass

        try:
            self.stability_monitor.update(packet)
            stability = self.stability_monitor.stability_index_percent()
        except Exception:
            stability = 0.0

        try:
            rec = self.recovery_health.update(packet)
            recovery = rec["status"]
        except Exception:
            recovery = "--"

        try:
            loss = self.sequencer.loss_rate_percent()
            fault = self.fault_detector.update(packet, loss)
            faults = fault["status"]
        except Exception:
            faults = "OK"

        try:
            self.mission_dashboard.update_ai(
                fingerprint, wind_str, landing_str, stability, recovery, faults)
        except Exception:
            pass

        self._ai_data = {
            "fingerprint": fingerprint,
            "wind": wind_data,
            "landing": landing_str,
            "stability": stability,
            "recovery": recovery,
            "faults": faults,
            "trend": getattr(self.trend_predictor, "prediction", None),
            "power": {
                "voltage": packet.get("VOLTAGE", 0.0),
                "current": packet.get("CURRENT", 0.0),
                "power":   packet.get("POWER", 0.0),
                "capacity": 0,
            },
        }

    # ---------------- Guidance ----------------
    def _update_guidance(self, packet):
        lat = packet.get("GNSS_LATITUDE")
        lon = packet.get("GNSS_LONGITUDE")
        if lat is None or lon is None:
            return
        if not self._guidance_reference_set:
            try:
                self.guidance_wind_estimator = GuidanceWindEstimator(lat, lon)
                self._guidance_reference_set = True
            except Exception:
                pass
        if self.guidance_wind_estimator:
            try:
                ws, wd = self.guidance_wind_estimator.update(
                    lat, lon, time.monotonic())
                self.guidance_dashboard.update_wind(ws, wd)
            except Exception:
                pass
        try:
            self.guidance_dashboard.update(packet)
        except Exception:
            pass

    # ---------------- Map ----------------
    def _update_map(self, packet):
        lat = packet.get("GNSS_LATITUDE")
        lon = packet.get("GNSS_LONGITUDE")
        if lat is None or lon is None:
            return
        try:
            self.flight_map.update_position(
                lat, lon, packet.get("PRED_LAT"), packet.get("PRED_LON"))
        except Exception:
            pass

    # ---------------- Commands ----------------
    def _send_cmd(self, cmd, raw: bool = False):
        if not (self.serial_link and self.serial_link.is_connected()):
            QtWidgets.QMessageBox.warning(
                self, "Not connected", "Connect to the LoRa receiver first.")
            return
        if not raw:
            line = build_uplink(cmd)
            try:
                seq = int(line.split(",")[1])
                self.command_tracker.sent(seq, cmd)
            except (ValueError, IndexError):
                pass
            self.serial_link.send_command(line)
        else:
            self.serial_link.send_command(cmd)
        self.bottom_status.setText(f"Sent: {cmd.strip()}")

    def _on_cmd_echo(self, line):
        parts = line.split(",")
        if len(parts) >= 3:
            try:
                seq = int(parts[1])
                self.command_tracker.ack(seq)
                self.bottom_status.setText(f"ACK: {parts[0]} = {parts[2]}")
            except (ValueError, IndexError):
                pass

    # ---------------- Calibration ----------------
    def _on_calibrate(self):
        if not (self.serial_link and self.serial_link.is_connected()):
            QtWidgets.QMessageBox.warning(self, "Not connected",
                                          "Connect before calibrating.")
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Calibrate",
            "Ensure CanSat is stationary on the ground.\nProceed?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply != QtWidgets.QMessageBox.Yes:
            return
        self._send_cmd(CMD_CALIBRATE)
        self.status_label.setText("STATUS: CALIBRATING")
        self.status_label.setStyleSheet("color: #f0a030; font-weight: bold;")

    def _on_calibration_complete(self, line):
        self.status_label.setText("STATUS: CALIBRATED")
        self.status_label.setStyleSheet("color: #60c090; font-weight: bold;")
        QtWidgets.QMessageBox.information(self, "Calibration", line)

    def _on_calibration_failed(self, line):
        self.status_label.setText("STATUS: CALIB FAILED")
        self.status_label.setStyleSheet("color: #e06050; font-weight: bold;")
        QtWidgets.QMessageBox.critical(self, "Calibration failed", line)

    # ---------------- Link health ----------------
    def _update_link_health(self):
        now = time.monotonic()
        age = (now - self._last_packet_monotonic
               if self._last_packet_monotonic else 999)
        if age < 1.2:
            color, state = "#00C853", "OK"
        elif age < 3.0:
            color, state = "#FFB300", "SLOW"
        else:
            color, state = "#D50000", "LOST"
        self.link_led.setStyleSheet(f"color: {color}; font-size: 20px;")

        self._packet_times.append(now)
        self._packet_times = [t for t in self._packet_times if now - t <= 10.0]
        rate = len(self._packet_times) / 10.0
        self.link_rate_label.setText(f"{rate:.1f} Hz ({state})")

        for seq, name in self.command_tracker.timed_out():
            self.bottom_status.setText(f"CMD TIMEOUT: {name} (seq {seq})")

    # ---------------- Report ----------------
    def _generate_report(self):
        self.report_status.setText("Generating...")
        try:
            ai_data = dict(self._ai_data)
            rg = ReportGenerator(
                csv_filepath=self.csv_logger.filepath,
                ai_data=ai_data,
                graph_engine=self.graph_engine,
            )
            out = rg.generate()
            self.report_status.setText(f"Saved: {out}")
            QtWidgets.QMessageBox.information(self, "Report",
                                              f"Report saved:\n{out}")
        except Exception as e:
            logger.exception("Report generation failed")
            self.report_status.setText(f"Error: {e}")
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    # ---------------- Close ----------------
    def closeEvent(self, event):
        for t in ("health_timer", "poll_timer"):
            try:
                getattr(self, t).stop()
            except Exception:
                pass
        if self.serial_link:
            self.serial_link.disconnect()
        self.csv_logger.close()
        logger.info("Application closed")
        event.accept()
