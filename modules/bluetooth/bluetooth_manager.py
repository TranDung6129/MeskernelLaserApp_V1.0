"""
Bluetooth Manager - Class quản lý kết nối Bluetooth
Hỗ trợ đa nền tảng (Ubuntu và Windows)
"""
import threading
import time
import platform
import re
from typing import Optional, List, Dict, Callable
from PyQt6.QtCore import QObject, pyqtSignal

# PyBluez có thể không khả dụng trên Windows (lỗi build). Thử import an toàn
try:
    import bluetooth  # type: ignore
except Exception:  # ImportError hoặc lỗi môi trường build
    bluetooth = None  # type: ignore

# Sử dụng pyserial làm backend trên Windows cho SPP qua COM port
try:
    import serial
    from serial.tools import list_ports
except Exception:
    serial = None  # type: ignore
    list_ports = None  # type: ignore


DEFAULT_SERIAL_BAUDRATE = 115200


class SerialSocketAdapter:
    """Adapter cung cấp API tương tự bluetooth.BluetoothSocket cho pyserial.Serial"""

    def __init__(self, com_port: str, baudrate: int = DEFAULT_SERIAL_BAUDRATE, timeout: float = 1.0):
        if serial is None:
            raise RuntimeError("PySerial chưa được cài đặt")
        # open rỗng, để set timeout trước khi open
        self._serial = serial.Serial()
        self._serial.port = com_port
        self._serial.baudrate = baudrate
        self._serial.timeout = timeout
        # Giảm độ trễ đọc liên byte để gom frame nhanh hơn trên Windows
        try:
            self._serial.inter_byte_timeout = 0.02
        except Exception:
            pass
        # Tắt mọi kiểu flow control để tránh chặn buffer trên SPP
        try:
            self._serial.rtscts = False
            self._serial.dsrdtr = False
            self._serial.xonxoff = False
        except Exception:
            pass
        self._serial.write_timeout = 1.0
        self._serial.open()
        # Cho Windows driver ổn định kết nối SPP
        try:
            time.sleep(0.1)
        except Exception:
            pass
        # Xóa dữ liệu tồn trong buffer ngay sau khi mở
        try:
            self._serial.reset_input_buffer()
            self._serial.reset_output_buffer()
        except Exception:
            pass
        # Tăng buffer nếu có API này trên Windows
        try:
            if hasattr(self._serial, "set_buffer_size"):
                self._serial.set_buffer_size(rx_size=8192, tx_size=8192)
        except Exception:
            pass

    def settimeout(self, timeout: float):
        self._serial.timeout = timeout

    def connect(self, address_port_tuple):
        # Giữ giao diện tương đồng; trên serial đã open khi __init__
        return

    def send(self, data: bytes):
        written = self._serial.write(data)
        try:
            self._serial.flush()
        except Exception:
            pass
        return written

    def recv(self, num_bytes: int) -> bytes:
        return self._serial.read(num_bytes)

    def close(self):
        try:
            self._serial.close()
        except Exception:
            pass

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
        # socket kiểu tổng quát (BluetoothSocket hoặc SerialSocketAdapter)
        self.socket: Optional[object] = None
        self.connected_device: Optional[BluetoothDevice] = None
        self.is_scanning = False
        self.receive_thread: Optional[threading.Thread] = None
        self.stop_receive = False
        # Quyết định backend dựa trên nền tảng và khả dụng của PyBluez
        self._is_windows = platform.system().lower().startswith("win")
        self._pybluez_available = bluetooth is not None
        self._use_serial_backend = self._is_windows and not self._pybluez_available
        
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
            if not self._use_serial_backend and self._pybluez_available:
                print(f"Đang quét thiết bị Bluetooth trong {duration} giây...")
                nearby_devices = bluetooth.discover_devices(  # type: ignore[attr-defined]
                    duration=duration, 
                    lookup_names=True, 
                    flush_cache=True
                )
                for addr, name in nearby_devices:
                    device = BluetoothDevice(addr, name)
                    devices.append(device)
                    self.device_found.emit(device)
            else:
                # Windows + không có PyBluez: duyệt COM ports để tìm SPP
                if list_ports is None:
                    raise RuntimeError("Không thể liệt kê cổng serial (pyserial thiếu)")
                print("Đang liệt kê cổng COM có thể là Bluetooth SPP...")
                for port in list_ports.comports():
                    description = port.description or "Serial Port"
                    # Heuristic: Windows thường hiển thị "Standard Serial over Bluetooth link"
                    is_bt = any(s in description.lower() for s in [
                        "bluetooth", "spp", "standard serial over bluetooth"
                    ])
                    if is_bt:
                        device = BluetoothDevice(port.device, f"{description}")
                        devices.append(device)
                        self.device_found.emit(device)
                
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
            # Trên backend serial/COM không có khái niệm dịch vụ
            if self._use_serial_backend or not self._pybluez_available:
                return []

            print(f"Đang tìm dịch vụ trên thiết bị {device_address}...")
            services = bluetooth.find_service(  # type: ignore[attr-defined]
                uuid="00001101-0000-1000-8000-00805f9b34fb",
                address=device_address
            )
            if not services:
                services = bluetooth.find_service(address=device_address)  # type: ignore[attr-defined]
            print(f"Tìm thấy {len(services)} dịch vụ")
            return services
        except Exception as e:
            error_msg = f"Lỗi khi tìm dịch vụ: {str(e)}"
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

            # Quyết định backend theo input và khả dụng
            is_mac_like = bool(re.match(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$", device_address))
            use_pybluez = self._pybluez_available and not self._use_serial_backend and is_mac_like

            if use_pybluez:
                # Tìm port nếu chưa được chỉ định
                if port is None or port == 0:
                    services = self.find_services(device_address)
                    if not services:
                        self.error_occurred.emit("Không tìm thấy dịch vụ RFCOMM")
                        return False
                    port = services[0].get("port", 1)

                print(f"Đang kết nối đến {device_address} trên port {port} (PyBluez)...")
                self.socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)  # type: ignore[attr-defined]
                self.socket.connect((device_address, port))
            else:
                # Windows/COM hoặc người dùng nhập COMx
                com_port = device_address
                baudrate = DEFAULT_SERIAL_BAUDRATE
                print(f"Đang kết nối đến {com_port} (Serial/COM, {baudrate} bps)...")
                self.socket = SerialSocketAdapter(com_port, baudrate=baudrate, timeout=1.0)

            self.connected_device = BluetoothDevice(device_address)
            print("Kết nối thành công")
            # Bắt đầu thread nhận dữ liệu
            self.start_receive_thread()
            self.connection_established.emit(device_address)
            return True

        except Exception as e:
            error_msg = f"Lỗi kết nối: {str(e)}"
            self.error_occurred.emit(error_msg)
            if self.socket:
                try:
                    self.socket.close()
                finally:
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
                # Cả BluetoothSocket và SerialSocketAdapter đều hỗ trợ settimeout
                if hasattr(self.socket, "settimeout"):
                    self.socket.settimeout(0.2)
                data = self.socket.recv(1024)
                
                if data:
                    # Rút gọn log nhận dữ liệu
                    self.data_received.emit(data)
                    
            except Exception as e:
                # Với Bluetooth: timeout ném BluetoothError; với Serial: trả về b'' khi timeout
                # Chỉ báo lỗi nếu không phải timeout
                if "timed out" in str(e).lower():
                    continue
                error_msg = f"Lỗi nhận dữ liệu: {str(e)}"
                self.error_occurred.emit(error_msg)
                break
        
        print("Thread nhận dữ liệu đã dừng")
    
    def is_connected(self) -> bool:
        """Kiểm tra trạng thái kết nối"""
        return self.socket is not None and self.connected_device is not None
    
    def get_connected_device(self) -> Optional[BluetoothDevice]:
        """Lấy thông tin thiết bị đang kết nối"""
        return self.connected_device