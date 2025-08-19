"""
Connection Panel - Panel điều khiển kết nối Bluetooth
"""
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, 
    QLabel, QSpinBox, QGroupBox, QFormLayout
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt
from ..bluetooth import BluetoothDevice
from .device_list_widget import DeviceListWidget

class ConnectionPanel(QWidget):
    """Panel điều khiển kết nối Bluetooth"""
    
    # Signals
    connection_requested = pyqtSignal(str, int)  # address, port
    disconnection_requested = pyqtSignal()
    device_scan_requested = pyqtSignal(int)  # duration
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.connect_signals()
        
    def setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        
        # === Device Discovery Section ===
        self.device_list_widget = DeviceListWidget()
        layout.addWidget(self.device_list_widget)
        
        # === Manual Connection Section ===
        manual_group = QGroupBox("Kết Nối Thủ Công")
        manual_layout = QFormLayout(manual_group)
        
        self.device_address_input = QLineEdit()
        self.device_address_input.setPlaceholderText("EC:62:60:B6:A8:02")
        self.device_address_input.setText("EC:62:60:B6:A8:02")  # Default
        
        self.device_port_input = QSpinBox()
        self.device_port_input.setRange(0, 30)
        self.device_port_input.setValue(1)
        self.device_port_input.setSpecialValueText("Tự động")
        
        manual_layout.addRow("Địa chỉ MAC:", self.device_address_input)
        manual_layout.addRow("Port/Channel:", self.device_port_input)
        
        # Connection buttons
        button_layout = QHBoxLayout()
        
        self.connect_button = QPushButton("Kết Nối")
        self.connect_button.clicked.connect(self._on_connect_clicked)
        
        self.disconnect_button = QPushButton("Ngắt Kết Nối")
        self.disconnect_button.clicked.connect(self._on_disconnect_clicked)
        self.disconnect_button.setEnabled(False)
        
        button_layout.addWidget(self.connect_button)
        button_layout.addWidget(self.disconnect_button)
        
        manual_layout.addRow(button_layout)
        layout.addWidget(manual_group)
        
        # === Connection Status Section ===
        status_group = QGroupBox("Trạng Thái Kết Nối")
        status_layout = QVBoxLayout(status_group)
        
        self.connection_status = QLabel("Chưa kết nối")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        status_layout.addWidget(self.connection_status)
        
        layout.addWidget(status_group)
        
        # Spacer
        layout.addStretch()

        # Logo ở đáy panel
        try:
            logo_label = QLabel()
            logo_pix = QPixmap('atglogo.png')
            if not logo_pix.isNull():
                logo_label.setPixmap(logo_pix.scaledToWidth(250))
                logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
                logo_label.setContentsMargins(0, 0, 0, 24)
                layout.addWidget(logo_label)
        except Exception:
            pass
        
    def connect_signals(self):
        """Kết nối các signals"""
        self.device_list_widget.device_selected.connect(self._on_device_selected)
        self.device_list_widget.scan_requested.connect(self.device_scan_requested.emit)
        
    @pyqtSlot()
    def _on_connect_clicked(self):
        """Xử lý khi nhấn nút kết nối"""
        address = self.device_address_input.text().strip()
        if not address:
            return
            
        port = self.device_port_input.value() if self.device_port_input.value() > 0 else 0
        self.connection_requested.emit(address, port)
        
    @pyqtSlot()
    def _on_disconnect_clicked(self):
        """Xử lý khi nhấn nút ngắt kết nối"""
        self.disconnection_requested.emit()
        
    @pyqtSlot(BluetoothDevice)
    def _on_device_selected(self, device: BluetoothDevice):
        """Xử lý khi chọn thiết bị từ danh sách"""
        self.device_address_input.setText(device.address)
        # Tự động kết nối
        self._on_connect_clicked()
        
    def add_discovered_device(self, device: BluetoothDevice):
        """Thêm thiết bị vừa phát hiện"""
        self.device_list_widget.add_device(device)
        
    def clear_device_list(self):
        """Xóa danh sách thiết bị"""
        self.device_list_widget.clear_devices()
        
    def set_scanning_state(self, is_scanning: bool):
        """Thiết lập trạng thái scanning"""
        self.device_list_widget.set_scanning(is_scanning)
        
    def set_connection_state(self, is_connected: bool, device_address: str = ""):
        """Thiết lập trạng thái kết nối"""
        if is_connected:
            self.connection_status.setText(f"Đã kết nối: {device_address}")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
        else:
            self.connection_status.setText("Chưa kết nối")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            
    def set_connecting_state(self, is_connecting: bool):
        """Thiết lập trạng thái đang kết nối"""
        self.connect_button.setEnabled(not is_connecting)
        if is_connecting:
            self.connection_status.setText("Đang kết nối...")
            self.connection_status.setStyleSheet("color: orange; font-weight: bold;")
            
    def get_manual_connection_info(self) -> tuple[str, int]:
        """Lấy thông tin kết nối thủ công"""
        address = self.device_address_input.text().strip()
        port = self.device_port_input.value() if self.device_port_input.value() > 0 else 0
        return address, port