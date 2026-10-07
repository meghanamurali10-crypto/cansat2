"""Simulation tab — start / stop the synthetic flight engine."""
from PyQt5 import QtWidgets
from simulation.simulation_engine import SimulationEngine
from core.telemetry.constants import TEAM_ID


class SimulationTab(QtWidgets.QWidget):
    def __init__(self, packet_callback=None, parent=None):
        super().__init__(parent)
        self.packet_callback = packet_callback

        # Pass callback into engine — it fires on every synthetic packet
        self.engine = SimulationEngine(
            packet_callback=self._emit,
            team_id=TEAM_ID,
        )

        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("SIMULATION ENGINE")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #88aacc;")
        layout.addWidget(title)

        form = QtWidgets.QFormLayout()

        self.scenario = QtWidgets.QComboBox()
        self.scenario.addItems([
            "nominal",
            "gnss_loss",
            "power_fault",
            "flywheel_stall",
            "comm_loss",
        ])
        form.addRow("Scenario:", self.scenario)

        self.rate = QtWidgets.QDoubleSpinBox()
        self.rate.setRange(0.5, 20.0)
        self.rate.setValue(1.0)
        self.rate.setSingleStep(0.5)
        form.addRow("Rate (Hz):", self.rate)

        layout.addLayout(form)

        row = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("Start Synthetic")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        layout.addLayout(row)

        self.status = QtWidgets.QLabel("Idle")
        self.status.setStyleSheet("color: #8a9aaa;")
        layout.addWidget(self.status)
        layout.addStretch()

    # ------------------------------------------------------------------
    def _emit(self, line):
        """Called from the sim worker thread — forward to MainWindow."""
        if self.packet_callback:
            self.packet_callback(line)

    def _start(self):
        self.engine.start(
            scenario=self.scenario.currentText(),
            rate_hz=self.rate.value(),
        )
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status.setText(
            f"Running: {self.scenario.currentText()} "
            f"@ {self.rate.value()} Hz"
        )

    def _stop(self):
        self.engine.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status.setText("Stopped")
