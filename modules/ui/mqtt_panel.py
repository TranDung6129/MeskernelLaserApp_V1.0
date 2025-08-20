"""
MQTT Panel - Tab quản lý kết nối và publish dữ liệu lên MQTT
"""
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QSpinBox, QCheckBox, QTextEdit, QFileDialog,
    QComboBox
)
from PyQt6.QtCore import pyqtSlot

from ..mqtt.mqtt_publisher import MQTTPublisher


class MQTTPanel(QWidget):
    """Panel cấu hình và quản lý MQTT, hỗ trợ publish dữ liệu đo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.publisher: Optional[MQTTPublisher] = None
        self.is_connected: bool = False
        self.latest_data: Dict[str, Any] = {}
        self.latest_stats: Dict[str, Any] = {}

        self._setup_ui()
        self._connect_signals()

    # === UI setup ===
    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Connection group ---
        conn_group = QGroupBox("Kết nối MQTT")
        conn_layout = QGridLayout(conn_group)

        self.host_edit = QLineEdit("localhost")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(1883)
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.tls_cb = QCheckBox("Bật TLS")
        self.ca_path_edit = QLineEdit()
        self.ca_path_edit.setPlaceholderText("CA certificate path (tuỳ chọn)")
        self.ca_browse_btn = QPushButton("Chọn file...")
        self.ca_path_edit.setEnabled(False)
        self.ca_browse_btn.setEnabled(False)

        self.connect_btn = QPushButton("Kết nối")
        self.disconnect_btn = QPushButton("Ngắt kết nối")
        self.disconnect_btn.setEnabled(False)
        self.status_label = QLabel("Chưa kết nối")

        row = 0
        conn_layout.addWidget(QLabel("Host"), row, 0)
        conn_layout.addWidget(self.host_edit, row, 1)
        conn_layout.addWidget(QLabel("Port"), row, 2)
        conn_layout.addWidget(self.port_spin, row, 3)
        row += 1
        conn_layout.addWidget(QLabel("Username"), row, 0)
        conn_layout.addWidget(self.username_edit, row, 1)
        conn_layout.addWidget(QLabel("Password"), row, 2)
        conn_layout.addWidget(self.password_edit, row, 3)
        row += 1
        conn_layout.addWidget(self.tls_cb, row, 0)
        conn_layout.addWidget(self.ca_path_edit, row, 1, 1, 2)
        conn_layout.addWidget(self.ca_browse_btn, row, 3)
        row += 1
        conn_layout.addWidget(self.connect_btn, row, 0, 1, 2)
        conn_layout.addWidget(self.disconnect_btn, row, 2, 1, 2)
        row += 1
        conn_layout.addWidget(QLabel("Trạng thái:"), row, 0)
        conn_layout.addWidget(self.status_label, row, 1, 1, 3)

        layout.addWidget(conn_group)

        # --- Publish config group ---
        pub_group = QGroupBox("Cấu hình Publish")
        pub_layout = QGridLayout(pub_group)

        self.topic_edit = QLineEdit("sensors/laser")
        self.topic_edit.setToolTip("Có thể dùng placeholder, ví dụ: sensors/laser/{serial_number}")
        self.qos_combo = QComboBox()
        self.qos_combo.addItems(["0", "1", "2"])
        self.retain_cb = QCheckBox("Retain")
        self.auto_publish_cb = QCheckBox("Publish mỗi mẫu đo")
        self.auto_publish_cb.setChecked(False)

        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "JSON (đầy đủ)",
            "JSON (tối giản)",
            "Tuỳ biến (template)"
        ])
        self.template_edit = QTextEdit()
        self.template_edit.setPlaceholderText("Ví dụ: {\n  \"timestamp\": {timestamp},\n  \"distance_mm\": {distance_mm},\n  \"quality\": {signal_quality},\n  \"velocity_ms\": {velocity_ms}\n}")
        self.template_edit.setVisible(False)

        self.preview_edit = QTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setPlaceholderText("Xem trước payload sẽ publish")

        self.publish_now_btn = QPushButton("Publish ngay")
        self.publish_now_btn.setEnabled(False)

        row = 0
        pub_layout.addWidget(QLabel("Topic"), row, 0)
        pub_layout.addWidget(self.topic_edit, row, 1, 1, 3)
        row += 1
        pub_layout.addWidget(QLabel("QoS"), row, 0)
        pub_layout.addWidget(self.qos_combo, row, 1)
        pub_layout.addWidget(self.retain_cb, row, 2)
        pub_layout.addWidget(self.auto_publish_cb, row, 3)
        row += 1
        pub_layout.addWidget(QLabel("Định dạng"), row, 0)
        pub_layout.addWidget(self.format_combo, row, 1, 1, 3)
        row += 1
        pub_layout.addWidget(QLabel("Template"), row, 0)
        pub_layout.addWidget(self.template_edit, row, 1, 1, 3)
        row += 1
        pub_layout.addWidget(QLabel("Xem trước"), row, 0)
        pub_layout.addWidget(self.preview_edit, row, 1, 1, 3)
        row += 1
        pub_layout.addWidget(self.publish_now_btn, row, 3)

        layout.addWidget(pub_group)

        # --- Log group ---
        log_group = QGroupBox("Nhật ký Publish")
        log_layout = QVBoxLayout(log_group)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        log_controls = QHBoxLayout()
        self.clear_log_btn = QPushButton("Xoá log")
        log_controls.addStretch()
        log_controls.addWidget(self.clear_log_btn)
        log_layout.addWidget(self.log_edit)
        log_layout.addLayout(log_controls)
        layout.addWidget(log_group)

        layout.addStretch()

    def _connect_signals(self):
        self.tls_cb.stateChanged.connect(self._on_tls_toggled)
        self.ca_browse_btn.clicked.connect(self._browse_ca_file)
        self.connect_btn.clicked.connect(self._connect_broker)
        self.disconnect_btn.clicked.connect(self._disconnect_broker)
        self.publish_now_btn.clicked.connect(self._publish_now)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        self.clear_log_btn.clicked.connect(lambda: self.log_edit.clear())

    # === Event handlers ===
    def _on_tls_toggled(self, _state: int):
        enabled = self.tls_cb.isChecked()
        self.ca_path_edit.setEnabled(enabled)
        self.ca_browse_btn.setEnabled(enabled)

    def _browse_ca_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn CA certificate", "", "Certificates (*.crt *.pem);;All Files (*)")
        if path:
            self.ca_path_edit.setText(path)

    def _append_log(self, message: str):
        self.log_edit.append(message)

    def _set_connected_ui(self, connected: bool):
        self.is_connected = connected
        self.connect_btn.setEnabled(not connected)
        self.disconnect_btn.setEnabled(connected)
        self.publish_now_btn.setEnabled(connected)
        self.status_label.setText("Đã kết nối" if connected else "Chưa kết nối")

    def _connect_broker(self):
        try:
            host = self.host_edit.text().strip() or "localhost"
            port = int(self.port_spin.value())
            username = self.username_edit.text().strip() or None
            password = self.password_edit.text() or None
            tls_enabled = self.tls_cb.isChecked()
            ca_path = self.ca_path_edit.text().strip() or None

            self.publisher = MQTTPublisher(
                broker_host=host,
                broker_port=port,
                username=username,
                password=password,
                tls_enabled=tls_enabled,
                ca_certs=ca_path
            )
            ok = self.publisher.connect()
            if ok:
                self._set_connected_ui(True)
                self._append_log(f"[INFO] Kết nối MQTT thành công: {host}:{port}")
            else:
                self._append_log("[ERROR] Kết nối MQTT thất bại")
        except Exception as e:
            self._append_log(f"[ERROR] Lỗi kết nối MQTT: {e}")

    def _disconnect_broker(self):
        try:
            if self.publisher:
                self.publisher.disconnect()
            self._set_connected_ui(False)
            self._append_log("[INFO] Đã ngắt kết nối MQTT")
        except Exception as e:
            self._append_log(f"[ERROR] Lỗi ngắt kết nối: {e}")

    def _build_payload(self, data: Dict[str, Any]) -> str:
        fmt = self.format_combo.currentText()
        try:
            combined = {**self.latest_stats, **data}
            if fmt.startswith("JSON (đầy đủ)"):
                import json
                return json.dumps(combined, ensure_ascii=False)
            if fmt.startswith("JSON (tối giản)"):
                minimal = {
                    'timestamp': combined.get('timestamp'),
                    'distance_mm': combined.get('distance_mm'),
                    'signal_quality': combined.get('signal_quality'),
                    'velocity_ms': combined.get('velocity_ms')
                }
                import json
                return json.dumps(minimal, ensure_ascii=False)
            # Custom template: Python format with keys from data
            template = self.template_edit.toPlainText().strip()
            if not template:
                template = "{timestamp},{distance_mm},{signal_quality},{velocity_ms}"
            # Safe formatting: missing keys -> empty string
            class SafeDict(dict):
                def __missing__(self, key):
                    return ''
            return template.format_map(SafeDict(combined))
        except Exception as e:
            return f"[ERROR] Lỗi tạo payload: {e}"

    def _build_topic(self, data: Dict[str, Any]) -> str:
        topic_template = self.topic_edit.text().strip() or "sensors/laser"
        class SafeDict(dict):
            def __missing__(self, key):
                return ''
        try:
            combined = {**self.latest_stats, **data}
            return topic_template.format_map(SafeDict(combined))
        except Exception:
            return topic_template

    def _refresh_preview(self):
        if not self.latest_data:
            self.preview_edit.setPlainText("")
            return
        payload = self._build_payload(self.latest_data)
        topic = self._build_topic(self.latest_data)
        self.preview_edit.setPlainText(f"Topic: {topic}\n\n{payload}")

    def _on_format_changed(self, _index: int):
        is_template = self.format_combo.currentText().startswith("Tuỳ biến")
        self.template_edit.setVisible(is_template)
        self._refresh_preview()

    def _publish_now(self):
        if not self.publisher or not self.is_connected:
            self._append_log("[WARNING] Chưa kết nối MQTT")
            return
        if not self.latest_data:
            self._append_log("[WARNING] Chưa có dữ liệu để publish")
            return

        topic = self._build_topic(self.latest_data)
        payload = self._build_payload(self.latest_data)
        qos = int(self.qos_combo.currentText())
        retain = self.retain_cb.isChecked()

        ok = self.publisher.publish(topic, payload, qos=qos, retain=retain)
        if ok:
            self._append_log(f"[SUCCESS] Published → {topic}: {payload}")
        else:
            self._append_log(f"[ERROR] Publish thất bại → {topic}")

    # === Public API ===
    @pyqtSlot(dict)
    def on_new_processed_data(self, processed: Dict[str, Any]):
        """Nhận dữ liệu từ DataProcessor.new_data_processed để xem trước/publish."""
        self.latest_data = processed or {}
        self._refresh_preview()
        if self.auto_publish_cb.isChecked() and self.publisher and self.is_connected:
            self._publish_now()

    @pyqtSlot(dict)
    def on_statistics_updated(self, stats: Dict[str, Any]):
        """Nhận thống kê/metadata thiết bị để làm giàu payload và topic placeholders."""
        self.latest_stats = stats or {}
        self._refresh_preview()

    def disconnect(self):
        try:
            if self.publisher:
                self.publisher.disconnect()
        except Exception:
            pass
        finally:
            self._set_connected_ui(False)

