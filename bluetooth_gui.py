"""
Bluetooth GUI - Entry point cho giao diện người dùng PyQt6
"""
import sys
from PyQt6.QtWidgets import QApplication
from modules.ui import BluetoothMainWindow

# Backward compatibility
BluetoothGUI = BluetoothMainWindow

def main():
    """Hàm main để chạy ứng dụng"""
    app = QApplication(sys.argv)
    
    # Thiết lập style
    app.setStyle('Fusion')
    
    # Tạo và hiển thị window
    window = BluetoothGUI()
    window.show()
    
    # Chạy event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()