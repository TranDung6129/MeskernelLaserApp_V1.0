"""
Communication Panel - Panel giao tiếp dữ liệu Bluetooth
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QTextEdit, 
    QLineEdit, QGroupBox, QTabWidget, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont
from datetime import datetime

class DataDisplayWidget(QWidget):
    """Widget hiển thị dữ liệu nhận được"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        
        # Data display area
        self.data_display = QTextEdit()
        self.data_display.setReadOnly(True)
        self.data_display.setFont(QFont("Consolas", 10))
        layout.addWidget(self.data_display)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.clear_button = QPushButton("Xóa Dữ Liệu")
        self.clear_button.clicked.connect(self.clear_data)
        
        self.save_button = QPushButton("Lưu Dữ Liệu")
        self.save_button.clicked.connect(self._save_data)
        
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.save_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
    def append_received_data(self, data: str):
        """Thêm dữ liệu nhận được"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.data_display.append(f"[{timestamp}] << {data}")
        
    def append_sent_data(self, data: str):
        """Thêm dữ liệu đã gửi"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.data_display.append(f"[{timestamp}] >> {data}")
        
    def clear_data(self):
        """Xóa tất cả dữ liệu"""
        self.data_display.clear()
        
    def _save_data(self):
        """Lưu dữ liệu ra file"""
        # TODO: Implement file save dialog
        pass

class DataSendWidget(QWidget):
    """Widget gửi dữ liệu"""
    
    # Signals
    data_send_requested = pyqtSignal(str)
    device_command_requested = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        
        # Send input area
        send_layout = QHBoxLayout()
        
        self.send_input = QLineEdit()
        self.send_input.setPlaceholderText("Nhập dữ liệu cần gửi...")
        self.send_input.returnPressed.connect(self._send_data)
        
        self.send_button = QPushButton("Gửi")
        self.send_button.clicked.connect(self._send_data)
        self.send_button.setEnabled(False)
        
        send_layout.addWidget(self.send_input)
        send_layout.addWidget(self.send_button)
        
        layout.addLayout(send_layout)
        
        # Quick send buttons - Device Control Commands
        self._create_quick_send_section(layout)
        
    def _create_quick_send_section(self, parent_layout):
        """Tạo section cho các nút điều khiển thiết bị theo bố cục gọn gàng"""
        def _style_button(button: QPushButton):
            button.setMinimumHeight(32)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            return button

        # Laser Control Group
        laser_group = QGroupBox("Điều Khiển Laser")
        laser_layout = QHBoxLayout(laser_group)
        for label, command in [("Bật Laser", "LASER_ON"), ("Tắt Laser", "LASER_OFF")]:
            btn = _style_button(QPushButton(label))
            btn.clicked.connect(lambda checked, cmd=command: self._send_device_command(cmd))
            laser_layout.addWidget(btn)
        parent_layout.addWidget(laser_group)

        # Measurement Control Group (Grid)
        measurement_group = QGroupBox("Điều Khiển Đo")
        grid = QGridLayout(measurement_group)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        single_commands = [
            ("Đo đơn (Auto)", "SINGLE_AUTO_MEASURE"),
            ("Đo đơn (Thấp)", "SINGLE_LOW_SPEED_MEASURE"),
            ("Đo đơn (Cao)", "SINGLE_HIGH_SPEED_MEASURE"),
        ]
        continuous_commands = [
            ("Đo liên tục (Auto)", "CONTINUOUS_AUTO_MEASURE"),
            ("Đo liên tục (Thấp)", "CONTINUOUS_LOW_SPEED_MEASURE"),
            ("Đo liên tục (Cao)", "CONTINUOUS_HIGH_SPEED_MEASURE"),
            ("Thoát đo liên tục", "EXIT_CONTINUOUS_MODE"),
        ]

        # Add single measurement buttons (row 0)
        for col, (label, command) in enumerate(single_commands):
            btn = _style_button(QPushButton(label))
            btn.clicked.connect(lambda checked, cmd=command: self._send_device_command(cmd))
            grid.addWidget(btn, 0, col)

        # Add continuous measurement buttons (row 1)
        for col, (label, command) in enumerate(continuous_commands):
            btn = _style_button(QPushButton(label))
            btn.clicked.connect(lambda checked, cmd=command: self._send_device_command(cmd))
            grid.addWidget(btn, 1, col)

        parent_layout.addWidget(measurement_group)

        # Read commands group (Grid)
        read_group = QGroupBox("Đọc Thông Tin")
        read_grid = QGridLayout(read_group)
        read_grid.setHorizontalSpacing(12)
        read_grid.setVerticalSpacing(8)
        read_commands = [
            ("Đọc trạng thái", "READ_STATUS"),
            ("Phiên bản HW", "READ_HARDWARE_VERSION"),
            ("Phiên bản SW", "READ_SOFTWARE_VERSION"),
        ]
        for col, (label, command) in enumerate(read_commands):
            btn = _style_button(QPushButton(label))
            btn.clicked.connect(lambda checked, cmd=command: self._send_device_command(cmd))
            read_grid.addWidget(btn, 0, col)
        parent_layout.addWidget(read_group)
        
    def _send_data(self):
        """Gửi dữ liệu từ input"""
        text = self.send_input.text().strip()
        if text:
            self.data_send_requested.emit(text)
            self.send_input.clear()
            
    def _send_device_command(self, command: str):
        """Gửi lệnh điều khiển thiết bị"""
        self.device_command_requested.emit(command)
        
    def _send_quick_command(self, command: str):
        """Gửi lệnh nhanh (raw text)"""
        self.data_send_requested.emit(command)
        
    def set_send_enabled(self, enabled: bool):
        """Thiết lập trạng thái có thể gửi"""
        self.send_button.setEnabled(enabled)
        
        # Disable/enable quick buttons
        for child in self.findChildren(QPushButton):
            if child != self.send_button:
                child.setEnabled(enabled)

class LogWidget(QWidget):
    """Widget hiển thị log hệ thống"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_display)
        
        # Log controls
        control_layout = QHBoxLayout()
        
        self.clear_log_button = QPushButton("Xóa Log")
        self.clear_log_button.clicked.connect(self.clear_log)
        
        self.save_log_button = QPushButton("Lưu Log")
        self.save_log_button.clicked.connect(self._save_log)
        
        control_layout.addWidget(self.clear_log_button)
        control_layout.addWidget(self.save_log_button)
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
    def add_log_message(self, message: str, level: str = "INFO"):
        """Thêm tin nhắn log"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted_message = f"[{timestamp}] [{level}] {message}"
        
        # Màu sắc theo level
        if level == "ERROR":
            formatted_message = f'<span style="color: red;">{formatted_message}</span>'
        elif level == "WARNING":
            formatted_message = f'<span style="color: orange;">{formatted_message}</span>'
        elif level == "SUCCESS":
            formatted_message = f'<span style="color: green;">{formatted_message}</span>'
            
        self.log_display.append(formatted_message)
        
    def clear_log(self):
        """Xóa tất cả log"""
        self.log_display.clear()
        
    def _save_log(self):
        """Lưu log ra file"""
        # TODO: Implement file save dialog
        pass

class CommunicationPanel(QWidget):
    """Panel chính cho giao tiếp dữ liệu"""
    
    # Signals
    data_send_requested = pyqtSignal(str)
    device_command_requested = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # === Communication Tab ===
        comm_tab = QWidget()
        comm_layout = QVBoxLayout(comm_tab)
        
        # Data display
        display_group = QGroupBox("Dữ Liệu Nhận")
        display_layout = QVBoxLayout(display_group)
        
        self.data_display_widget = DataDisplayWidget()
        display_layout.addWidget(self.data_display_widget)
        
        comm_layout.addWidget(display_group)
        
        # Data send
        send_group = QGroupBox("Gửi Dữ Liệu")
        send_layout = QVBoxLayout(send_group)
        
        self.data_send_widget = DataSendWidget()
        send_layout.addWidget(self.data_send_widget)
        
        comm_layout.addWidget(send_group)
        
        self.tab_widget.addTab(comm_tab, "Giao Tiếp")
        
        # === Log Tab ===
        self.log_widget = LogWidget()
        self.tab_widget.addTab(self.log_widget, "Log")
        
        layout.addWidget(self.tab_widget)
        
    def connect_signals(self):
        """Kết nối các signals"""
        self.data_send_widget.data_send_requested.connect(self.data_send_requested.emit)
        self.data_send_widget.device_command_requested.connect(self.device_command_requested.emit)
        
    def on_data_received(self, data: str):
        """Xử lý khi nhận được dữ liệu"""
        self.data_display_widget.append_received_data(data)
        self.log_widget.add_log_message(f"Nhận: {data}", "INFO")
        
    def on_data_sent(self, data: str):
        """Xử lý khi gửi dữ liệu (text hoặc hex)"""
        self.data_display_widget.append_sent_data(data)
        self.log_widget.add_log_message(f"Gửi: {data}", "INFO")
        
    def on_command_sent(self, command_bytes: bytes, command_description: str):
        """Xử lý khi gửi lệnh (bytes)"""
        from ..core.response_parser import MeskernelResponseParser
        
        # Hiển thị hex trong data box
        hex_string = MeskernelResponseParser.bytes_to_hex_string(command_bytes)
        self.data_display_widget.append_sent_data(hex_string)
        
        # Hiển thị mô tả có ý nghĩa trong log
        self.log_widget.add_log_message(f"Gửi lệnh: {command_description}", "INFO")
        
    def on_error_occurred(self, error_message: str):
        """Xử lý khi có lỗi"""
        self.log_widget.add_log_message(error_message, "ERROR")
        
    def on_connection_changed(self, is_connected: bool):
        """Xử lý khi trạng thái kết nối thay đổi"""
        self.data_send_widget.set_send_enabled(is_connected)
        
        if is_connected:
            self.log_widget.add_log_message("Kết nối thành công", "SUCCESS")
        else:
            self.log_widget.add_log_message("Đã ngắt kết nối", "WARNING")
            
    def add_log_message(self, message: str, level: str = "INFO"):
        """Thêm message vào log"""
        self.log_widget.add_log_message(message, level)