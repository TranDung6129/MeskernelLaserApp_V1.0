"""
Main Window - Cửa sổ chính của ứng dụng Bluetooth
"""
import threading
import os
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter, QMessageBox, QStatusBar,
    QFileDialog, QToolBar, QToolButton, QStyle, QSplitterHandle
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QUrl
from PyQt6.QtGui import QCloseEvent, QAction, QKeySequence, QDesktopServices

from ..bluetooth import BluetoothManager, BluetoothDevice
from ..core import LaserDeviceController, LaserCommand, CommandType, MeskernelResponseParser
from ..processing import DataProcessor, VelocityCalculator, MeasurementData
from ..sensor.constants import (
    LEN_STATUS_RESPONSE,
    LEN_VERSION_RESPONSE,
    LEN_SERIAL_RESPONSE,
    LEN_VOLTAGE_RESPONSE,
    LEN_MEASUREMENT_RESPONSE,
    LEN_LASER_CONTROL_RESPONSE,
    HEADER,
)
from .connection_panel import ConnectionPanel
from .communication_panel import CommunicationPanel
from .charts_panel import ChartsPanel # type: ignore
from .mqtt_panel import MQTTPanel
from .geotech_panel import GeotechPanel

class ToggleSplitterHandle(QSplitterHandle):
    def __init__(self, orientation, splitter, host_window):
        super().__init__(orientation, splitter)
        self._host = host_window
        self._btn = QToolButton(self)
        self._btn.setAutoRaise(True)
        try:
            self._btn.setFixedSize(18, 36)
        except Exception:
            pass
        self._btn.clicked.connect(self._on_clicked)
        self._refresh_style()

    def resizeEvent(self, event):  # type: ignore[override]
        try:
            bw = self._btn.width()
            bh = self._btn.height()
            x = (self.width() - bw) // 2
            y = (self.height() - bh) // 2
            self._btn.move(x, y)
        except Exception:
            pass
        return super().resizeEvent(event)

    def _on_clicked(self):
        try:
            self._host._on_toolbar_toggle_connection()
            self._refresh_style()
        except Exception:
            pass

    def _refresh_style(self):
        try:
            visible = self._host.connection_panel.isVisible()
            # Không dùng icon, dùng chữ với màu đậm
            self._btn.setText("Ẩn" if visible else "Hiện")
            self._btn.setToolTip("Ẩn panel kết nối" if visible else "Hiện panel kết nối")
            # Màu đậm: nền xám đậm, chữ trắng
            self._btn.setStyleSheet(
                "QToolButton { background-color: #444; color: white; border: 1px solid #222; border-radius: 4px; padding: 2px 6px; }"
                "QToolButton:hover { background-color: #555; }"
                "QToolButton:pressed { background-color: #333; }"
            )
        except Exception:
            pass

class ToggleSplitter(QSplitter):
    def __init__(self, orientation, host_window):
        super().__init__(orientation)
        self._host = host_window

    def createHandle(self):  # type: ignore[override]
        return ToggleSplitterHandle(self.orientation(), self, self._host)


class BluetoothMainWindow(QMainWindow):
    """Cửa sổ chính của ứng dụng Bluetooth"""
    
    def __init__(self):
        super().__init__()
        self.bluetooth_manager = BluetoothManager()
        self.device_controller = LaserDeviceController()
        self.last_command_type = None  # Track last command để parse response
        self._bt_parse_buffer = bytearray()
        
        # Data processing
        self.data_processor = DataProcessor(max_samples=1000)
        self.velocity_calculator = VelocityCalculator(window_size=5)
        
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Thiết lập giao diện người dùng"""
        self.setWindowTitle("Laser Device Manager - Aitogy")
        self.setGeometry(100, 100, 1400, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        splitter = ToggleSplitter(Qt.Orientation.Horizontal, self)
        self.splitter = splitter
        try:
            self.splitter.setCollapsible(0, True)
        except Exception:
            pass
        main_layout.addWidget(splitter)
        # Track left panel sizing for collapse/restore
        self._left_panel_width_prev = 220
        self._left_collapsed = False
        
        # Left panel
        self.connection_panel = ConnectionPanel()
        splitter.addWidget(self.connection_panel)
        
        # Right panel - Tabs
        from PyQt6.QtWidgets import QTabWidget
        self.tab_widget = QTabWidget()
        
        # Add tabs
        self.communication_panel = CommunicationPanel()
        self.charts_panel = ChartsPanel()
        self.mqtt_panel = MQTTPanel()
        self.geotech_panel = GeotechPanel()
        
        self.tab_widget.addTab(self.communication_panel, "Giao Tiếp")
        self.tab_widget.addTab(self.charts_panel, "Đồ Thị/Thống Kê")
        self.tab_widget.addTab(self.mqtt_panel, "MQTT")
        self.tab_widget.addTab(self.geotech_panel, "Phân Tích Khoan")
        
        splitter.addWidget(self.tab_widget)
        splitter.setSizes([220, 1180])
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Sẵn sàng")

        # Menus
        self._create_menus()
        
    def connect_signals(self):
        """Kết nối các signals"""
        # Connection panel signals
        self.connection_panel.connection_requested.connect(self._handle_connection_request)
        self.connection_panel.disconnection_requested.connect(self._handle_disconnection_request)
        self.connection_panel.device_scan_requested.connect(self._handle_scan_request)
        
        # Communication panel signals
        self.communication_panel.data_send_requested.connect(self._handle_send_request)
        self.communication_panel.device_command_requested.connect(self._handle_device_command)
        
        # Bluetooth manager signals
        self.bluetooth_manager.device_found.connect(self._on_device_found)
        self.bluetooth_manager.connection_established.connect(self._on_connection_established)
        self.bluetooth_manager.connection_lost.connect(self._on_connection_lost)
        self.bluetooth_manager.data_received.connect(self._on_data_received)
        self.bluetooth_manager.error_occurred.connect(self._on_error_occurred)
        
        # Device controller signals
        self.device_controller.measurement_data_received.connect(self._on_measurement_data)
        self.device_controller.device_status_changed.connect(self._on_device_status_changed)
        self.device_controller.command_executed.connect(self._on_command_executed)
        self.device_controller.error_occurred.connect(self._on_error_occurred)
        
        # Data processor signals
        self.data_processor.new_data_processed.connect(self.charts_panel.update_measurement_data)
        # Cấp dữ liệu đã xử lý cho MQTT panel để preview/publish
        self.data_processor.new_data_processed.connect(self.mqtt_panel.on_new_processed_data)
        # Cấp dữ liệu cho panel khoan địa chất
        self.data_processor.new_data_processed.connect(self.geotech_panel.on_new_processed_data)
        self.data_processor.statistics_updated.connect(self.charts_panel.update_statistics)
        self.data_processor.statistics_updated.connect(self.mqtt_panel.on_statistics_updated)
        self.data_processor.statistics_updated.connect(self.geotech_panel.on_statistics_updated)

        # Wire DataProcessor into ChartsPanel widgets that need it
        try:
            self.charts_panel.set_data_processor(self.data_processor)
        except Exception:
            pass

        # Khi có phản hồi dạng bytes từ Bluetooth (được parse ở controller), cập nhật thống kê thiết bị nếu phù hợp
        
    # === Menus ===
    def _create_menus(self):
        # File menu
        file_menu = self.menuBar().addMenu("&Tệp")

        self.act_export_csv = QAction("Xuất dữ liệu gần đây...", self)
        self.act_export_csv.setShortcut(QKeySequence("Ctrl+E"))
        self.act_export_csv.triggered.connect(self._action_export_csv)
        file_menu.addAction(self.act_export_csv)

        self.act_clear_data = QAction("Xoá dữ liệu", self)
        self.act_clear_data.setShortcut(QKeySequence("Ctrl+L"))
        self.act_clear_data.triggered.connect(self._action_clear_data)
        file_menu.addAction(self.act_clear_data)

        file_menu.addSeparator()

        self.act_quit = QAction("Thoát", self)
        self.act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_quit.triggered.connect(self.close)
        file_menu.addAction(self.act_quit)

        # Device menu
        device_menu = self.menuBar().addMenu("&Thiết bị")

        self.act_scan = QAction("Quét thiết bị", self)
        self.act_scan.setShortcut(QKeySequence("F5"))
        self.act_scan.triggered.connect(self._action_scan_devices)
        device_menu.addAction(self.act_scan)

        self.act_connect = QAction("Kết nối", self)
        self.act_connect.setShortcut(QKeySequence("Ctrl+K"))
        self.act_connect.triggered.connect(self._action_connect_device)
        device_menu.addAction(self.act_connect)

        self.act_disconnect = QAction("Ngắt kết nối", self)
        self.act_disconnect.setShortcut(QKeySequence("Ctrl+Shift+K"))
        self.act_disconnect.triggered.connect(self._action_disconnect_device)
        device_menu.addAction(self.act_disconnect)

        # MQTT menu
        mqtt_menu = self.menuBar().addMenu("&MQTT")

        self.act_mqtt_connect = QAction("Kết nối Broker", self)
        self.act_mqtt_connect.triggered.connect(self._action_mqtt_connect)
        mqtt_menu.addAction(self.act_mqtt_connect)

        self.act_mqtt_disconnect = QAction("Ngắt kết nối Broker", self)
        self.act_mqtt_disconnect.triggered.connect(self._action_mqtt_disconnect)
        mqtt_menu.addAction(self.act_mqtt_disconnect)

        # View menu
        view_menu = self.menuBar().addMenu("&Hiển thị")

        self.act_toggle_connection_panel = QAction("Panel kết nối", self)
        self.act_toggle_connection_panel.setCheckable(True)
        self.act_toggle_connection_panel.setChecked(True)
        self.act_toggle_connection_panel.triggered.connect(self._action_toggle_connection_panel)
        view_menu.addAction(self.act_toggle_connection_panel)

        self.act_toggle_status_bar = QAction("Thanh trạng thái", self)
        self.act_toggle_status_bar.setCheckable(True)
        self.act_toggle_status_bar.setChecked(True)
        self.act_toggle_status_bar.triggered.connect(self._action_toggle_status_bar)
        view_menu.addAction(self.act_toggle_status_bar)

        # Help menu
        help_menu = self.menuBar().addMenu("&Trợ giúp")

        self.act_about = QAction("Giới thiệu", self)
        self.act_about.triggered.connect(self._action_about)
        help_menu.addAction(self.act_about)

        self.act_open_manual = QAction("Mở Hướng dẫn sử dụng", self)
        self.act_open_manual.setShortcut(QKeySequence("F1"))
        self.act_open_manual.triggered.connect(self._action_open_manual)
        help_menu.addAction(self.act_open_manual)

        # Quick tab switching
        self._add_view_tab_shortcuts(view_menu)

        # Fullscreen toggle
        self.act_fullscreen = QAction("Chế độ toàn màn hình", self)
        self.act_fullscreen.setCheckable(True)
        self.act_fullscreen.setShortcut(QKeySequence("F11"))
        self.act_fullscreen.triggered.connect(self._action_toggle_fullscreen)
        view_menu.addAction(self.act_fullscreen)

    def _create_toolbar(self):
        try:
            toolbar = QToolBar("Tác vụ nhanh", self)
            toolbar.setMovable(False)
            self.addToolBar(toolbar)

            # Arrow button to toggle connection panel visibility
            self.btn_toggle_conn = QToolButton(self)
            self.btn_toggle_conn.setAutoRaise(True)
            self.btn_toggle_conn.clicked.connect(self._on_toolbar_toggle_connection)
            toolbar.addWidget(self.btn_toggle_conn)
            self._update_toggle_btn_icon()
        except Exception:
            pass

    def _is_connection_collapsed(self) -> bool:
        try:
            return bool(self._left_collapsed)
        except Exception:
            return False

    def _update_toggle_btn_icon(self):
        try:
            collapsed = self._is_connection_collapsed()
            icon = self.style().standardIcon(
                QStyle.StandardPixmap.SP_ArrowRight if collapsed else QStyle.StandardPixmap.SP_ArrowLeft
            )
            self.btn_toggle_conn.setIcon(icon)
            self.btn_toggle_conn.setToolTip("Hiện panel kết nối" if collapsed else "Ẩn panel kết nối")
        except Exception:
            pass

    def _on_toolbar_toggle_connection(self):
        try:
            self._set_connection_panel_collapsed(not self._is_connection_collapsed())
        except Exception:
            pass

    def _set_connection_panel_collapsed(self, collapsed: bool):
        try:
            # Always keep widget visible, only change sizes to preserve handle
            try:
                self.connection_panel.setVisible(True)
            except Exception:
                pass

            sizes = self.splitter.sizes()
            total = sum(sizes) if sizes else max(1, self.width())

            if collapsed:
                # Save current left width if > 0 to restore later
                try:
                    if sizes and sizes[0] > 0:
                        self._left_panel_width_prev = sizes[0]
                except Exception:
                    pass
                left = 0
                right = max(1, total - left)
                self.splitter.setSizes([left, right])
            else:
                left = max(180, int(self._left_panel_width_prev))
                right = max(1, total - left)
                self.splitter.setSizes([left, right])

            self._left_collapsed = collapsed
            # Sync menu action check state: checked means shown
            try:
                self.act_toggle_connection_panel.setChecked(not collapsed)
            except Exception:
                pass
            self._update_toggle_btn_icon()
        except Exception:
            pass

    # === Menu actions handlers ===
    def _action_export_csv(self):
        try:
            default_path, _ = QFileDialog.getSaveFileName(
                self,
                "Xuất dữ liệu CSV",
                "measurement_export.csv",
                "CSV Files (*.csv)"
            )
            if not default_path:
                return
            ok = self.data_processor.export_data_csv(default_path)
            if ok:
                QMessageBox.information(self, "Thành công", f"Đã xuất dữ liệu: {default_path}")
            else:
                QMessageBox.warning(self, "Lỗi", "Không thể xuất dữ liệu")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Xuất dữ liệu thất bại: {e}")

    def _action_clear_data(self):
        try:
            self.data_processor.clear_data()
            # Thông báo UI cập nhật
            self.data_processor.statistics_updated.emit(self.data_processor.get_current_stats())
            # Xoá đồ thị
            self.charts_panel.clear_all_data()
            # Geotech preview/series sẽ tự làm rỗng sau phiên mới, chỉ cần xoá biểu đồ hiện thời
            try:
                self.geotech_panel._clear_chart()
            except Exception:
                pass
            self.status_bar.showMessage("Đã xoá dữ liệu")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể xoá dữ liệu: {e}")

    def _action_scan_devices(self):
        try:
            duration = 8
            try:
                duration = self.connection_panel.device_list_widget.scan_duration.value()
            except Exception:
                pass
            self._handle_scan_request(duration)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu quét: {e}")

    def _action_connect_device(self):
        try:
            address, port = self.connection_panel.get_manual_connection_info()
            self._handle_connection_request(address, port)
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể kết nối: {e}")

    def _action_disconnect_device(self):
        try:
            self._handle_disconnection_request()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể ngắt kết nối: {e}")

    def _action_mqtt_connect(self):
        try:
            # Kích hoạt hành vi nút để tận dụng logic sẵn có
            self.mqtt_panel.connect_btn.click()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể kết nối MQTT: {e}")

    def _action_mqtt_disconnect(self):
        try:
            self.mqtt_panel.disconnect_btn.click()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể ngắt MQTT: {e}")

    def _action_toggle_connection_panel(self, checked: bool):
        try:
            self._set_connection_panel_collapsed(not checked)
        except Exception:
            pass

    def _action_toggle_status_bar(self, checked: bool):
        try:
            self.statusBar().setVisible(checked)
        except Exception:
            pass

    def _action_about(self):
        try:
            QMessageBox.information(
                self,
                "Giới thiệu",
                "Laser Device Manager\nPhiên bản 1.0.0\n\nAitogy"
            )
        except Exception:
            pass

    def _action_open_manual(self):
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            manual_path = os.path.join(base_dir, 'Meskernel User Manual LDJG_v1.1_en.pdf')
            if os.path.exists(manual_path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(manual_path))
            else:
                QMessageBox.warning(self, "Không tìm thấy", "Không tìm thấy file hướng dẫn sử dụng.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể mở hướng dẫn: {e}")

    def _add_view_tab_shortcuts(self, view_menu):
        # Switch to tabs quickly
        self.act_tab_comm = QAction("Chuyển tới tab: Giao Tiếp", self)
        self.act_tab_comm.setShortcut(QKeySequence("Ctrl+1"))
        self.act_tab_comm.triggered.connect(lambda: self.tab_widget.setCurrentIndex(0))
        view_menu.addAction(self.act_tab_comm)

        self.act_tab_charts = QAction("Chuyển tới tab: Đồ Thị/Thống Kê", self)
        self.act_tab_charts.setShortcut(QKeySequence("Ctrl+2"))
        self.act_tab_charts.triggered.connect(lambda: self.tab_widget.setCurrentIndex(1))
        view_menu.addAction(self.act_tab_charts)

        self.act_tab_mqtt = QAction("Chuyển tới tab: MQTT", self)
        self.act_tab_mqtt.setShortcut(QKeySequence("Ctrl+3"))
        self.act_tab_mqtt.triggered.connect(lambda: self.tab_widget.setCurrentIndex(2))
        view_menu.addAction(self.act_tab_mqtt)

        self.act_tab_geotech = QAction("Chuyển tới tab: Phân Tích Khoan", self)
        self.act_tab_geotech.setShortcut(QKeySequence("Ctrl+4"))
        self.act_tab_geotech.triggered.connect(lambda: self.tab_widget.setCurrentIndex(3))
        view_menu.addAction(self.act_tab_geotech)

    def _action_toggle_fullscreen(self, checked: bool):
        try:
            if checked:
                self.showFullScreen()
            else:
                self.showNormal()
        except Exception:
            pass
    @pyqtSlot(str, int)
    def _handle_connection_request(self, address: str, port: int):
        """Xử lý yêu cầu kết nối"""
        if not address:
            self._show_error("Vui lòng nhập địa chỉ MAC của thiết bị")
            return
            
        self.connection_panel.set_connecting_state(True)
        self.communication_panel.add_log_message(f"Đang kết nối đến {address}...")
        
        # Kết nối trong thread riêng
        connect_thread = threading.Thread(
            target=self._connect_worker,
            args=(address, port if port > 0 else None)
        )
        connect_thread.daemon = True
        connect_thread.start()
        
    def _connect_worker(self, address: str, port: Optional[int]):
        """Worker để kết nối trong thread riêng"""
        success = self.bluetooth_manager.connect_to_device(address, port)
        if not success:
            # Reset connecting state if failed
            self.connection_panel.set_connecting_state(False)
            
    @pyqtSlot()
    def _handle_disconnection_request(self):
        """Xử lý yêu cầu ngắt kết nối"""
        self.bluetooth_manager.disconnect()
        
    @pyqtSlot(int)
    def _handle_scan_request(self, duration: int):
        """Xử lý yêu cầu quét thiết bị"""
        if self.bluetooth_manager.is_scanning:
            return
            
        self.connection_panel.clear_device_list()
        self.connection_panel.set_scanning_state(True)
        self.communication_panel.add_log_message(f"Bắt đầu quét thiết bị trong {duration} giây...")
        
        # Quét trong thread riêng
        scan_thread = threading.Thread(
            target=self._scan_worker,
            args=(duration,)
        )
        scan_thread.daemon = True
        scan_thread.start()
        
        # Timer để reset UI sau khi scan xong
        QTimer.singleShot(duration * 1000 + 1000, self._scan_finished)
        
    def _scan_worker(self, duration: int):
        """Worker để quét thiết bị trong thread riêng"""
        self.bluetooth_manager.scan_devices(duration)
        
    def _scan_finished(self):
        """Callback khi quét xong"""
        self.connection_panel.set_scanning_state(False)
        self.communication_panel.add_log_message("Quét thiết bị hoàn tất")
        
    @pyqtSlot(str)
    def _handle_send_request(self, data: str):
        """Xử lý yêu cầu gửi dữ liệu raw"""
        if not self.bluetooth_manager.is_connected():
            self._show_error("Chưa kết nối đến thiết bị")
            return
            
        if self.bluetooth_manager.send_data(data):
            self.communication_panel.on_data_sent(data)
        else:
            self._show_error("Không thể gửi dữ liệu")
            
    @pyqtSlot(str)
    def _handle_device_command(self, command_type: str):
        """Xử lý lệnh điều khiển thiết bị"""
        if not self.device_controller.is_connected():
            self._show_error("Chưa kết nối đến thiết bị")
            return
            
        try:
            # Convert string to CommandType enum
            cmd_type = CommandType(command_type)
            command = LaserCommand(command_type=cmd_type)
            
            # Track command type để parse response
            self.last_command_type = cmd_type.value
            
            # Hiển thị lệnh đã gửi dạng hex trong data box và mô tả trong log
            command_bytes = command.to_bytes()
            if command_bytes:
                self.communication_panel.on_command_sent(command_bytes, command.description or str(cmd_type.value))
            
            success = self.device_controller.execute_command(command)
            if success:
                self.communication_panel.add_log_message(f"Thực thi thành công: {command.description or str(cmd_type.value)}", "SUCCESS")
            else:
                self.communication_panel.add_log_message(f"Lỗi thực thi: {command.description or str(cmd_type.value)}", "ERROR")
                
        except ValueError:
            self._show_error(f"Lệnh không hợp lệ: {command_type}")
            
    # === Bluetooth Manager Event Handlers ===
    
    @pyqtSlot(BluetoothDevice)
    def _on_device_found(self, device: BluetoothDevice):
        """Callback khi tìm thấy thiết bị"""
        self.connection_panel.add_discovered_device(device)
        self.communication_panel.add_log_message(f"Tìm thấy thiết bị: {device}")
        
    @pyqtSlot(str)
    def _on_connection_established(self, device_address: str):
        """Callback khi kết nối thành công"""
        self.connection_panel.set_connection_state(True, device_address)
        self.communication_panel.on_connection_changed(True)
        self.status_bar.showMessage(f"Đã kết nối đến {device_address}")
        
        # Connect device controller to bluetooth
        self.device_controller.connect_bluetooth(self.bluetooth_manager)
        self._bt_parse_buffer.clear()

        # Auto query device info
        try:
            query_cmds = [
                LaserCommand(command_type=CommandType.READ_STATUS),
                LaserCommand(command_type=CommandType.READ_HARDWARE_VERSION),
                LaserCommand(command_type=CommandType.READ_SOFTWARE_VERSION),
                LaserCommand(command_type=CommandType.READ_SERIAL_NUMBER),
                LaserCommand(command_type=CommandType.READ_INPUT_VOLTAGE)
            ]
            QTimer.singleShot(300, lambda: self._send_query_sequence(query_cmds, 0))
        except Exception as e:
            self.communication_panel.add_log_message(f"Không thể truy vấn thông tin thiết bị: {e}", "WARNING")

    def _send_query_sequence(self, commands, index: int = 0):
        """Gửi lần lượt các lệnh truy vấn"""
        if index >= len(commands):
            return
        try:
            cmd = commands[index]
            self.last_command_type = cmd.command_type.value
            cmd_bytes = cmd.to_bytes()
            if cmd_bytes and self.bluetooth_manager and self.bluetooth_manager.socket:
                self.bluetooth_manager.socket.send(cmd_bytes)
            QTimer.singleShot(300, lambda: self._send_query_sequence(commands, index + 1))
        except Exception as e:
            self.communication_panel.add_log_message(f"Lỗi gửi truy vấn: {e}", "WARNING")
        
    @pyqtSlot(str)
    def _on_connection_lost(self, device_address: str):
        """Callback khi mất kết nối"""
        self.connection_panel.set_connection_state(False)
        self.communication_panel.on_connection_changed(False)
        self.status_bar.showMessage("Không có kết nối")
        
        # Disconnect device controller
        self.device_controller.disconnect()
        
    @pyqtSlot(bytes)
    def _on_data_received(self, data: bytes):
        """Callback khi nhận được dữ liệu"""
        try:
            # Hiển thị hex data trong data box
            hex_string = MeskernelResponseParser.bytes_to_hex_string(data)
            self.communication_panel.on_data_received(hex_string)
            
            # Ghép buffer để tách frame khi thiết bị trả về nhiều gói trong một lần recv
            self._bt_parse_buffer.extend(data)
            parsed_info = {}
            
            # Nếu đang chờ phản hồi cho một lệnh cụ thể, tách frame theo độ dài mong đợi
            if self.last_command_type:
                expected_len_map = {
                    'READ_STATUS': LEN_STATUS_RESPONSE,
                    'READ_HARDWARE_VERSION': LEN_VERSION_RESPONSE,
                    'READ_SOFTWARE_VERSION': LEN_VERSION_RESPONSE,
                    'READ_SERIAL_NUMBER': LEN_SERIAL_RESPONSE,
                    'READ_INPUT_VOLTAGE': LEN_VOLTAGE_RESPONSE,
                    'READ_LAST_MEASUREMENT': LEN_MEASUREMENT_RESPONSE,
                    'LASER_ON': LEN_LASER_CONTROL_RESPONSE,
                    'LASER_OFF': LEN_LASER_CONTROL_RESPONSE,
                }
                expected_len = expected_len_map.get(self.last_command_type, 0)
                
                while True:
                    start_idx = self._bt_parse_buffer.find(HEADER)
                    if start_idx == -1:
                        # Không có header trong buffer, xóa rác
                        self._bt_parse_buffer.clear()
                        break
                    if len(self._bt_parse_buffer) - start_idx < expected_len or expected_len == 0:
                        # Chưa đủ dữ liệu cho frame mong đợi
                        # Giữ từ header trở đi
                        if start_idx > 0:
                            del self._bt_parse_buffer[:start_idx]
                        break
                    candidate = bytes(self._bt_parse_buffer[start_idx:start_idx + expected_len])
                    parsed_info = MeskernelResponseParser.parse_response_with_context(candidate, self.last_command_type)
                    # Dù parse được hay không, bỏ frame này để tránh kẹt
                    del self._bt_parse_buffer[:start_idx + expected_len]
                    # Reset context sau lần thử đầu tiên để không khóa các gói kế tiếp
                    self.last_command_type = None
                    break
            
            # Nếu không có context hoặc chưa parse ra gì, thử auto-detect một frame ở đầu buffer
            if not parsed_info:
                # Thử cắt frame theo prefix 4 byte để xác định chính xác độ dài mong đợi
                while True:
                    start_idx = self._bt_parse_buffer.find(HEADER)
                    if start_idx == -1:
                        self._bt_parse_buffer.clear()
                        break
                    remaining = len(self._bt_parse_buffer) - start_idx
                    if remaining < 4:
                        # Chưa đủ để nhận diện loại frame, giữ lại từ header
                        if start_idx > 0:
                            del self._bt_parse_buffer[:start_idx]
                        break
                    prefix = bytes(self._bt_parse_buffer[start_idx:start_idx + 4])
                    expected_len = None
                    if prefix == b'\xAA\x00\x00\x22':
                        expected_len = LEN_MEASUREMENT_RESPONSE
                    elif prefix == b'\xAA\x80\x00\x00':
                        expected_len = LEN_STATUS_RESPONSE
                    elif prefix == b'\xAA\x80\x00\x06':
                        expected_len = LEN_VOLTAGE_RESPONSE
                    elif prefix == b'\xAA\x80\x00\x0A':
                        expected_len = LEN_VERSION_RESPONSE
                    elif prefix == b'\xAA\x80\x00\x0C':
                        expected_len = LEN_VERSION_RESPONSE
                    elif prefix == b'\xAA\x80\x00\x0E':
                        expected_len = LEN_SERIAL_RESPONSE
                    else:
                        # Không nhận diện được: thử ưu tiên measurement nếu còn đủ dữ liệu
                        if remaining >= LEN_MEASUREMENT_RESPONSE:
                            expected_len = LEN_MEASUREMENT_RESPONSE
                        elif remaining >= LEN_STATUS_RESPONSE:
                            expected_len = LEN_STATUS_RESPONSE
                        else:
                            if start_idx > 0:
                                del self._bt_parse_buffer[:start_idx]
                            break

                    if remaining < (expected_len or 0):
                        # Chưa đủ dữ liệu cho frame mong đợi
                        if start_idx > 0:
                            del self._bt_parse_buffer[:start_idx]
                        break

                    candidate = bytes(self._bt_parse_buffer[start_idx:start_idx + expected_len])
                    del self._bt_parse_buffer[:start_idx + expected_len]
                    parsed_info = MeskernelResponseParser.parse_any_response(candidate)
                    break
                
            if "error" in parsed_info:
                self.communication_panel.add_log_message(f"Parse error: {parsed_info['error']}", "ERROR")
            else:
                # Hiển thị thông tin đã parse trong log
                if "full_info" in parsed_info:
                    self.communication_panel.add_log_message(parsed_info["full_info"], "INFO")
                else:
                    self.communication_panel.add_log_message(f"Response: {hex_string}", "INFO")

                # Cập nhật DataProcessor với thông tin thiết bị để xóa trạng thái Unknown
                if 'voltage' in parsed_info:
                    self.data_processor.update_device_info('input_voltage', float(parsed_info['voltage']))
                if 'version_type' in parsed_info and parsed_info['version_type'] == 'Hardware':
                    self.data_processor.update_device_info('hardware_version', parsed_info.get('version_string', 'Unknown'))
                if 'version_type' in parsed_info and parsed_info['version_type'] == 'Software':
                    self.data_processor.update_device_info('software_version', parsed_info.get('version_string', 'Unknown'))
                if 'serial_number' in parsed_info:
                    self.data_processor.update_device_info('serial_number', parsed_info.get('serial_number', 'Unknown'))
                if 'status_text' in parsed_info:
                    self.data_processor.update_device_info('device_status', parsed_info.get('status_text', 'Unknown'))
                    
        except Exception as e:
            self.communication_panel.on_error_occurred(f"Lỗi xử lý dữ liệu: {e}")
            
    @pyqtSlot(str)
    def _on_error_occurred(self, error_message: str):
        """Callback khi có lỗi"""
        self.communication_panel.on_error_occurred(error_message)
        self.status_bar.showMessage(f"Lỗi: {error_message}")
        
    # === Device Controller Event Handlers ===
    
    @pyqtSlot(dict)
    def _on_measurement_data(self, measurement: dict):
        """Callback khi nhận được dữ liệu đo"""
        # Debug: nhận dữ liệu đo
        # print(f"Main window received measurement: {measurement}")
        distance = measurement.get('distance_mm', 0)
        quality = measurement.get('signal_quality', 0)
        
        # Nếu có raw data thì hiển thị hex, nếu không thì hiển thị formatted
        if 'raw_data' in measurement:
            hex_data = MeskernelResponseParser.bytes_to_hex_string(measurement['raw_data'])
            self.communication_panel.on_data_received(hex_data)
        else:
            formatted_data = f"Measurement: {distance:.1f}mm, Q:{quality}%"
            self.communication_panel.on_data_received(formatted_data)
        
        # Log với thông tin có ý nghĩa
        log_message = f"Đo được: {distance:.1f}mm, Chất lượng tín hiệu: {quality}%"
        self.communication_panel.add_log_message(log_message, "SUCCESS")
        
        # Process data cho charts và velocity calculation
        import time
        measurement_obj = MeasurementData(
            timestamp=time.time(),
            distance_mm=distance,
            signal_quality=quality
        )
        
        # Tính velocity và lấy bản smooth theo window
        _ = self.velocity_calculator.add_measurement(measurement_obj)
        smoothed_velocity = self.velocity_calculator.get_smoothed_velocity()
        velocity = smoothed_velocity if smoothed_velocity is not None else _
        if velocity is None:
            velocity = 0.0

        # Thêm vào data processor cùng timestamp và vận tốc để tính state/hysteresis
        self.data_processor.add_measurement(
            distance,
            quality,
            velocity_ms=float(velocity),
            timestamp=measurement_obj.timestamp,
        )
        
        # Update status bar with latest measurement
        velocity_text = f", V:{velocity:.3f}m/s" if velocity is not None else ""
        self.status_bar.showMessage(f"Đo được: {distance:.1f}mm (Q:{quality}%){velocity_text}")
        
    @pyqtSlot(str)
    def _on_device_status_changed(self, status: str):
        """Callback khi trạng thái thiết bị thay đổi"""
        self.communication_panel.add_log_message(f"Trạng thái thiết bị: {status}", "INFO")
        # Đồng bộ vào bảng thống kê
        self.data_processor.update_device_info('device_status', status)
        
    @pyqtSlot(str, bool)
    def _on_command_executed(self, command: str, success: bool):
        """Callback khi lệnh được thực thi"""
        level = "SUCCESS" if success else "ERROR"
        result = "thành công" if success else "thất bại"
        self.communication_panel.add_log_message(f"Lệnh '{command}' {result}", level)
        
    # === Utility Methods ===
    
    def _show_error(self, message: str):
        """Hiển thị thông báo lỗi"""
        QMessageBox.warning(self, "Lỗi", message)
        self.communication_panel.on_error_occurred(message)
        
    def _show_info(self, message: str):
        """Hiển thị thông báo thông tin"""
        QMessageBox.information(self, "Thông tin", message)
        
    # === Window Events ===
    
    def closeEvent(self, event: QCloseEvent):
        """Xử lý khi đóng cửa sổ"""
        if self.bluetooth_manager.is_connected():
            reply = QMessageBox.question(
                self, 
                "Xác nhận", 
                "Bạn có muốn ngắt kết nối trước khi thoát?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.bluetooth_manager.disconnect()
        # Đảm bảo ngắt MQTT nếu đang bật
        try:
            self.mqtt_panel.disconnect()
        except Exception:
            pass
                
        event.accept()
        
    # === Public Methods ===
    
    def get_bluetooth_manager(self) -> BluetoothManager:
        """Lấy bluetooth manager"""
        return self.bluetooth_manager
        
    def is_connected(self) -> bool:
        """Kiểm tra trạng thái kết nối"""
        return self.bluetooth_manager.is_connected()
        
    def get_connected_device_address(self) -> Optional[str]:
        """Lấy địa chỉ thiết bị đang kết nối"""
        device = self.bluetooth_manager.get_connected_device()
        return device.address if device else None