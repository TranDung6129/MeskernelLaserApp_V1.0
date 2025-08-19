"""
Main Window - Cửa sổ chính của ứng dụng Bluetooth
"""
import threading
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter, QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QCloseEvent

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
        
        # Main layout với splitter
        main_layout = QHBoxLayout(central_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Panel trái - Kết nối
        self.connection_panel = ConnectionPanel()
        splitter.addWidget(self.connection_panel)
        
        # Panel phải - Tabs cho Communication và Charts
        from PyQt6.QtWidgets import QTabWidget
        self.tab_widget = QTabWidget()
        
        # Tab 1: Communication
        self.communication_panel = CommunicationPanel()
        self.tab_widget.addTab(self.communication_panel, "Giao Tiếp")
        
        # Tab 2: Charts & Stats
        self.charts_panel = ChartsPanel()
        self.tab_widget.addTab(self.charts_panel, "Đồ Thị & Thống Kê")
        
        splitter.addWidget(self.tab_widget)
        
        # Thiết lập tỷ lệ - Thu nhỏ panel kết nối
        splitter.setSizes([300, 1100])
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Sẵn sàng")
        
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
        self.data_processor.statistics_updated.connect(self.charts_panel.update_statistics)

        # Khi có phản hồi dạng bytes từ Bluetooth (được parse ở controller), cập nhật thống kê thiết bị nếu phù hợp
        
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

        # Tự động truy vấn thông tin thiết bị cơ bản để điền thống kê còn Unknown (gửi tuần tự)
        try:
            query_cmds = [
                LaserCommand(command_type=CommandType.READ_STATUS),
                LaserCommand(command_type=CommandType.READ_HARDWARE_VERSION),
                LaserCommand(command_type=CommandType.READ_SOFTWARE_VERSION),
                LaserCommand(command_type=CommandType.READ_SERIAL_NUMBER),
                LaserCommand(command_type=CommandType.READ_INPUT_VOLTAGE)
            ]
            self._send_query_sequence(query_cmds, 0)
        except Exception as e:
            self.communication_panel.add_log_message(f"Không thể truy vấn thông tin thiết bị tự động: {e}", "WARNING")

    def _send_query_sequence(self, commands, index: int = 0):
        """Gửi lần lượt các lệnh truy vấn với delay ngắn để đảm bảo parse đúng context"""
        if index >= len(commands):
            return
        try:
            cmd = commands[index]
            self.last_command_type = cmd.command_type.value
            cmd_bytes = cmd.to_bytes()
            if cmd_bytes and self.bluetooth_manager and self.bluetooth_manager.socket:
                self.bluetooth_manager.socket.send(cmd_bytes)
            # Gửi lệnh kế tiếp sau 150ms
            QTimer.singleShot(150, lambda: self._send_query_sequence(commands, index + 1))
        except Exception as e:
            self.communication_panel.add_log_message(f"Lỗi gửi truy vấn tự động: {e}", "WARNING")
        
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
                # Thử cắt một frame 9 hoặc 13 bytes theo header
                while True:
                    start_idx = self._bt_parse_buffer.find(HEADER)
                    if start_idx == -1:
                        self._bt_parse_buffer.clear()
                        break
                    remaining = len(self._bt_parse_buffer) - start_idx
                    candidate = None
                    if remaining >= LEN_MEASUREMENT_RESPONSE:
                        candidate = bytes(self._bt_parse_buffer[start_idx:start_idx + LEN_MEASUREMENT_RESPONSE])
                        del self._bt_parse_buffer[:start_idx + LEN_MEASUREMENT_RESPONSE]
                    elif remaining >= LEN_STATUS_RESPONSE:
                        candidate = bytes(self._bt_parse_buffer[start_idx:start_idx + LEN_STATUS_RESPONSE])
                        del self._bt_parse_buffer[:start_idx + LEN_STATUS_RESPONSE]
                    else:
                        if start_idx > 0:
                            del self._bt_parse_buffer[:start_idx]
                        break
                    if candidate:
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
        
        # Tính velocity
        velocity = self.velocity_calculator.add_measurement(measurement_obj)
        
        # Update velocity trong stats TRƯỚC khi add vào data processor
        if velocity is not None:
            self.data_processor.stats['current_velocity'] = velocity
        else:
            self.data_processor.stats['current_velocity'] = 0.0
            
        # Bây giờ add vào data processor (sẽ emit signal với velocity đã update)
        self.data_processor.add_measurement(distance, quality)
        
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