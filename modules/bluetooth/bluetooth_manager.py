"""
Bluetooth Manager - Class quản lý kết nối Bluetooth
Hỗ trợ đa nền tảng (Ubuntu và Windows)
"""
import bluetooth
import threading
import time
from typing import Optional, List, Dict, Callable
from PyQt6.QtCore import QObject, pyqtSignal

class BluetoothDevice:
    """Lớp đại diện cho một thiết bị Bluetooth"""
    def __init__(self, address: str, name: str = "Unknown Device"):
        self.address = address
        self.name = name
        self.services = []
        
    def __str__(self):
        return f"{self.name} ({self.address})"

class BluetoothManager(QObject):
    """Class quản lý kết nối Bluetooth"""
    
    # Signals để giao tiếp với GUI
    device_found = pyqtSignal(BluetoothDevice)
    connection_established = pyqtSignal(str)  # device address
    connection_lost = pyqtSignal(str)
    data_received = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.socket: Optional[bluetooth.BluetoothSocket] = None
        self.connected_device: Optional[BluetoothDevice] = None
        self.is_scanning = False
        self.receive_thread: Optional[threading.Thread] = None
        self.stop_receive = False
        
    def scan_devices(self, duration: int = 8) -> List[BluetoothDevice]:
        """
        Quét các thiết bị Bluetooth trong vùng
        
        Args:
            duration: Thời gian quét (giây)
            
        Returns:
            List các thiết bị tìm được
        """
        devices = []
        self.is_scanning = True
        
        try:
            print(f"Đang quét thiết bị Bluetooth trong {duration} giây...")
            nearby_devices = bluetooth.discover_devices(
                duration=duration, 
                lookup_names=True, 
                flush_cache=True
            )
            
            for addr, name in nearby_devices:
                device = BluetoothDevice(addr, name)
                devices.append(device)
                self.device_found.emit(device)
                # Rút gọn log: phát hiện thiết bị
                
        except Exception as e:
            error_msg = f"Lỗi khi quét thiết bị: {str(e)}"
            # Rút gọn log lỗi
            self.error_occurred.emit(error_msg)
        finally:
            self.is_scanning = False
            
        return devices
    
    def find_services(self, device_address: str) -> List[Dict]:
        """
        Tìm các dịch vụ RFCOMM trên thiết bị
        
        Args:
            device_address: Địa chỉ MAC của thiết bị
            
        Returns:
            List các dịch vụ tìm được
        """
        try:
            print(f"Đang tìm dịch vụ trên thiết bị {device_address}...")
            
            # Tìm dịch vụ Serial Port Profile (SPP)
            services = bluetooth.find_service(
                uuid="00001101-0000-1000-8000-00805f9b34fb",
                address=device_address
            )
            
            if not services:
                # Thử tìm tất cả các dịch vụ
                services = bluetooth.find_service(address=device_address)
                
            print(f"Tìm thấy {len(services)} dịch vụ")
                
            return services
            
        except Exception as e:
            error_msg = f"Lỗi khi tìm dịch vụ: {str(e)}"
            # Rút gọn log lỗi
            self.error_occurred.emit(error_msg)
            return []
    
    def connect_to_device(self, device_address: str, port: Optional[int] = None) -> bool:
        """
        Kết nối đến thiết bị Bluetooth
        
        Args:
            device_address: Địa chỉ MAC của thiết bị
            port: Port/channel để kết nối (nếu None sẽ tự động tìm)
            
        Returns:
            True nếu kết nối thành công
        """
        try:
            if self.socket:
                self.disconnect()
                
            # Tìm port nếu chưa được chỉ định
            if port is None:
                services = self.find_services(device_address)
                if not services:
                    self.error_occurred.emit("Không tìm thấy dịch vụ RFCOMM")
                    return False
                port = services[0]["port"]
            
            print(f"Đang kết nối đến {device_address} trên port {port}...")
            
            # Tạo socket RFCOMM
            self.socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.socket.connect((device_address, port))
            
            self.connected_device = BluetoothDevice(device_address)
            print("Kết nối thành công")
            
            # Bắt đầu thread nhận dữ liệu
            self.start_receive_thread()
            
            self.connection_established.emit(device_address)
            return True
            
        except Exception as e:
            error_msg = f"Lỗi kết nối: {str(e)}"
            # Rút gọn log lỗi
            self.error_occurred.emit(error_msg)
            if self.socket:
                self.socket.close()
                self.socket = None
            return False
    
    def disconnect(self):
        """Ngắt kết nối Bluetooth"""
        if self.socket:
            try:
                print("Đang ngắt kết nối...")
                self.stop_receive = True
                
                if self.receive_thread and self.receive_thread.is_alive():
                    self.receive_thread.join(timeout=2)
                
                self.socket.close()
                self.socket = None
                
                if self.connected_device:
                    self.connection_lost.emit(self.connected_device.address)
                    self.connected_device = None
                    
                print("Đã ngắt kết nối")
                
            except Exception as e:
                print(f"Lỗi khi ngắt kết nối: {e}")
    
    def send_data(self, data: str) -> bool:
        """
        Gửi dữ liệu qua Bluetooth
        
        Args:
            data: Chuỗi dữ liệu cần gửi
            
        Returns:
            True nếu gửi thành công
        """
        if not self.socket:
            self.error_occurred.emit("Chưa kết nối đến thiết bị")
            return False
            
        try:
            self.socket.send(data.encode('utf-8'))
            return True
        except Exception as e:
            error_msg = f"Lỗi khi gửi dữ liệu: {str(e)}"
            # Rút gọn log lỗi
            self.error_occurred.emit(error_msg)
            return False
    
    def start_receive_thread(self):
        """Bắt đầu thread nhận dữ liệu"""
        self.stop_receive = False
        self.receive_thread = threading.Thread(target=self._receive_data_worker)
        self.receive_thread.daemon = True
        self.receive_thread.start()
    
    def _receive_data_worker(self):
        """Worker thread để nhận dữ liệu liên tục"""
        while not self.stop_receive and self.socket:
            try:
                # Set timeout để có thể kiểm tra stop_receive
                self.socket.settimeout(1.0)
                data = self.socket.recv(1024)
                
                if data:
                    # Rút gọn log nhận dữ liệu
                    self.data_received.emit(data)
                    
            except bluetooth.btcommon.BluetoothError as e:
                if "timed out" not in str(e).lower():
                    error_msg = f"Lỗi nhận dữ liệu: {str(e)}"
                    # Rút gọn log lỗi
                    self.error_occurred.emit(error_msg)
                    break
            except Exception as e:
                error_msg = f"Lỗi không mong đợi: {str(e)}"
                # Rút gọn log lỗi
                self.error_occurred.emit(error_msg)
                break
        
        print("Thread nhận dữ liệu đã dừng")
    
    def is_connected(self) -> bool:
        """Kiểm tra trạng thái kết nối"""
        return self.socket is not None and self.connected_device is not None
    
    def get_connected_device(self) -> Optional[BluetoothDevice]:
        """Lấy thông tin thiết bị đang kết nối"""
        return self.connected_device