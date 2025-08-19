"""
Device List Widget - Widget hiển thị danh sách thiết bị Bluetooth
"""
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, 
    QListWidgetItem, QProgressBar, QSpinBox, QLabel, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from ..bluetooth import BluetoothDevice

class DeviceListWidget(QWidget):
    """Widget hiển thị và quản lý danh sách thiết bị Bluetooth"""
    
    # Signals
    device_selected = pyqtSignal(BluetoothDevice)
    scan_requested = pyqtSignal(int)  # duration
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        
        # Group box
        group_box = QGroupBox("Quét Thiết Bị")
        group_layout = QVBoxLayout(group_box)
        
        # Scan controls
        scan_controls = QHBoxLayout()
        
        self.scan_button = QPushButton("Quét Thiết Bị")
        self.scan_button.clicked.connect(self._on_scan_clicked)
        
        self.scan_duration = QSpinBox()
        self.scan_duration.setRange(5, 30)
        self.scan_duration.setValue(8)
        self.scan_duration.setSuffix(" giây")
        
        scan_controls.addWidget(self.scan_button)
        scan_controls.addWidget(QLabel("Thời gian:"))
        scan_controls.addWidget(self.scan_duration)
        
        group_layout.addLayout(scan_controls)
        
        # Progress bar
        self.scan_progress = QProgressBar()
        self.scan_progress.setVisible(False)
        group_layout.addWidget(self.scan_progress)
        
        # Device list
        self.device_list = QListWidget()
        self.device_list.itemDoubleClicked.connect(self._on_device_double_clicked)
        group_layout.addWidget(self.device_list)
        
        # Refresh button
        self.refresh_button = QPushButton("Làm mới danh sách")
        self.refresh_button.clicked.connect(self.clear_devices)
        group_layout.addWidget(self.refresh_button)
        
        layout.addWidget(group_box)
        
    @pyqtSlot()
    def _on_scan_clicked(self):
        """Xử lý khi nhấn nút quét"""
        duration = self.scan_duration.value()
        self.scan_requested.emit(duration)
        
    @pyqtSlot(QListWidgetItem)
    def _on_device_double_clicked(self, item: QListWidgetItem):
        """Xử lý khi double-click vào thiết bị"""
        device = item.data(Qt.ItemDataRole.UserRole)
        if device:
            self.device_selected.emit(device)
            
    def add_device(self, device: BluetoothDevice):
        """Thêm thiết bị vào danh sách"""
        # Kiểm tra xem thiết bị đã có trong danh sách chưa
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            existing_device = item.data(Qt.ItemDataRole.UserRole)
            if existing_device and existing_device.address == device.address:
                # Cập nhật tên nếu cần
                item.setText(str(device))
                item.setData(Qt.ItemDataRole.UserRole, device)
                return
                
        # Thêm thiết bị mới
        item = QListWidgetItem(str(device))
        item.setData(Qt.ItemDataRole.UserRole, device)
        self.device_list.addItem(item)
        
    def clear_devices(self):
        """Xóa tất cả thiết bị khỏi danh sách"""
        self.device_list.clear()
        
    def set_scanning(self, is_scanning: bool):
        """Thiết lập trạng thái scanning"""
        self.scan_button.setEnabled(not is_scanning)
        self.scan_progress.setVisible(is_scanning)
        
        if is_scanning:
            self.scan_progress.setRange(0, 0)  # Indeterminate progress
        else:
            self.scan_progress.setRange(0, 100)
            self.scan_progress.setValue(0)
            
    def get_selected_device(self) -> Optional[BluetoothDevice]:
        """Lấy thiết bị đang được chọn"""
        current_item = self.device_list.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None
        
    def select_device_by_address(self, address: str):
        """Chọn thiết bị theo địa chỉ MAC"""
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            device = item.data(Qt.ItemDataRole.UserRole)
            if device and device.address == address:
                self.device_list.setCurrentItem(item)
                break