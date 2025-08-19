"""
Device Controller - Controller chính cho thiết bị laser
"""
import threading
import time
from typing import Optional, Callable, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal

from .commands import LaserCommand, CommandType
from ..bluetooth import BluetoothManager
from ..sensor import MeskernelSensor
from .response_parser import MeskernelResponseParser

class LaserDeviceController(QObject):
    """Controller chính cho thiết bị laser, hỗ trợ cả Bluetooth và Serial"""
    
    # Signals
    measurement_data_received = pyqtSignal(dict)  # {distance_mm, signal_quality, timestamp}
    device_status_changed = pyqtSignal(str)  # status string
    command_executed = pyqtSignal(str, bool)  # command, success
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.bluetooth_manager: Optional[BluetoothManager] = None
        self.serial_sensor: Optional[MeskernelSensor] = None
        self.connection_type: Optional[str] = None  # 'bluetooth' or 'serial'
        self.bluetooth_buffer: bytearray = bytearray()
        
        self.continuous_measuring = False
        self.measurement_thread: Optional[threading.Thread] = None
        self.stop_measurement = False
        
        # Device state
        self.laser_on = False
        self.measurement_rate = 10  # Hz
        self.device_info: Dict[str, Any] = {}
        
    def connect_bluetooth(self, bluetooth_manager: BluetoothManager) -> bool:
        """Kết nối qua Bluetooth"""
        try:
            self.bluetooth_manager = bluetooth_manager
            self.connection_type = 'bluetooth'
            self.bluetooth_buffer.clear()
            
            # Connect signals
            self.bluetooth_manager.data_received.connect(self._on_bluetooth_data_received)
            self.bluetooth_manager.error_occurred.connect(self.error_occurred.emit)
            
            self.device_status_changed.emit("Đã kết nối qua Bluetooth")
            return True
        except Exception as e:
            self.error_occurred.emit(f"Lỗi kết nối Bluetooth: {e}")
            return False
    
    def connect_serial(self, sensor: MeskernelSensor) -> bool:
        """Kết nối qua Serial"""
        try:
            self.serial_sensor = sensor
            self.connection_type = 'serial'
            
            self.device_status_changed.emit("Đã kết nối qua Serial")
            return True
        except Exception as e:
            self.error_occurred.emit(f"Lỗi kết nối Serial: {e}")
            return False
    
    def disconnect(self):
        """Ngắt kết nối"""
        self.stop_continuous_measurement()
        
        if self.bluetooth_manager:
            self.bluetooth_manager.disconnect()
            self.bluetooth_manager = None
            
        if self.serial_sensor:
            self.serial_sensor.close()
            self.serial_sensor = None
            
        self.connection_type = None
        self.device_status_changed.emit("Đã ngắt kết nối")
    
    def execute_command(self, command: LaserCommand) -> bool:
        """Thực thi lệnh điều khiển"""
        try:
            if not self.is_connected():
                self.error_occurred.emit("Chưa kết nối đến thiết bị")
                return False
            
            command_bytes = command.to_bytes()
            success = False
            
            if self.connection_type == 'bluetooth' and self.bluetooth_manager:
                # Send raw bytes for Bluetooth
                success = self.bluetooth_manager.socket.send(command_bytes) if self.bluetooth_manager.socket else False
            elif self.connection_type == 'serial' and self.serial_sensor:
                success = self._execute_serial_command(command)
            
            # Update internal state based on command
            self._update_device_state(command, success)
            
            self.command_executed.emit(str(command.command_type.value), success)
            return success
            
        except Exception as e:
            self.error_occurred.emit(f"Lỗi thực thi lệnh: {e}")
            return False
    
    def _execute_serial_command(self, command: LaserCommand) -> bool:
        """Thực thi lệnh qua Serial"""
        if not self.serial_sensor:
            return False
            
        try:
            command_bytes = command.to_bytes()
            if not command_bytes:
                return False
                
            # Send command via serial
            self.serial_sensor.ser.write(command_bytes)
            self.serial_sensor.ser.flush()
            
            # Handle specific command types
            if command.command_type in [CommandType.CONTINUOUS_AUTO_MEASURE, 
                                      CommandType.CONTINUOUS_LOW_SPEED_MEASURE,
                                      CommandType.CONTINUOUS_HIGH_SPEED_MEASURE]:
                self.start_continuous_measurement()
                return True
            elif command.command_type == CommandType.EXIT_CONTINUOUS_MODE:
                self.stop_continuous_measurement()
                return True
            elif command.command_type in [CommandType.SINGLE_AUTO_MEASURE,
                                        CommandType.SINGLE_LOW_SPEED_MEASURE, 
                                        CommandType.SINGLE_HIGH_SPEED_MEASURE]:
                # Wait for response
                expected_len = command.get_expected_response_length()
                if expected_len > 0:
                    response = self.serial_sensor.ser.read(expected_len)
                    if len(response) == expected_len:
                        # Use our response parser instead
                        from .response_parser import MeskernelResponseParser
                        parsed_data = MeskernelResponseParser.parse_measurement_response(response)
                        if "error" not in parsed_data:
                            # Add raw data for hex display
                            parsed_data["raw_data"] = response
                            self.measurement_data_received.emit(parsed_data)
                return True
            else:
                # For read commands, wait for response
                expected_len = command.get_expected_response_length()
                if expected_len > 0:
                    response = self.serial_sensor.ser.read(expected_len)
                    return len(response) == expected_len
                return True
                
        except Exception as e:
            self.error_occurred.emit(f"Lỗi lệnh Serial: {e}")
            return False
    
    def _update_device_state(self, command: LaserCommand, success: bool):
        """Cập nhật trạng thái thiết bị sau khi thực thi lệnh"""
        if not success:
            return
            
        if command.command_type == CommandType.LASER_ON:
            self.laser_on = True
            self.device_status_changed.emit("Laser đã bật")
        elif command.command_type == CommandType.LASER_OFF:
            self.laser_on = False
            self.device_status_changed.emit("Laser đã tắt")
        elif command.command_type in [CommandType.CONTINUOUS_AUTO_MEASURE,
                                     CommandType.CONTINUOUS_LOW_SPEED_MEASURE,
                                     CommandType.CONTINUOUS_HIGH_SPEED_MEASURE]:
            self.device_status_changed.emit(f"Bắt đầu đo liên tục - {command.description}")
        elif command.command_type == CommandType.EXIT_CONTINUOUS_MODE:
            self.device_status_changed.emit("Đã thoát chế độ đo liên tục")
    
    def start_continuous_measurement(self):
        """Bắt đầu đo liên tục"""
        if self.continuous_measuring:
            return
            
        self.continuous_measuring = True
        self.stop_measurement = False
        
        if self.connection_type == 'serial' and self.serial_sensor:
            self.measurement_thread = threading.Thread(target=self._continuous_measurement_worker)
            self.measurement_thread.daemon = True
            self.measurement_thread.start()
            
        self.device_status_changed.emit("Đang đo liên tục")
    
    def stop_continuous_measurement(self):
        """Dừng đo liên tục"""
        if not self.continuous_measuring:
            return
            
        self.continuous_measuring = False
        self.stop_measurement = True
        
        if self.measurement_thread and self.measurement_thread.is_alive():
            self.measurement_thread.join(timeout=2)
            
        self.device_status_changed.emit("Đã dừng đo liên tục")
    
    def _continuous_measurement_worker(self):
        """Worker thread cho đo liên tục"""
        while self.continuous_measuring and not self.stop_measurement:
            try:
                if self.serial_sensor:
                    measurement = self.serial_sensor.read_measurement_packet(timeout=1.0)
                    if measurement:
                        self.measurement_data_received.emit(measurement)
                        
                time.sleep(1.0 / self.measurement_rate)  # Delay based on measurement rate
                
            except Exception as e:
                self.error_occurred.emit(f"Lỗi đo liên tục: {e}")
                break
    
    def _on_bluetooth_data_received(self, data: bytes):
        """Xử lý dữ liệu nhận từ Bluetooth"""
        try:
            # 1) Thử parse dạng text (nếu thiết bị gửi chuỗi ASCII)
            text = None
            try:
                text = data.decode('utf-8', errors='ignore').strip()
            except Exception:
                text = None

            if text:
                if 'DISTANCE:' in text:
                    parts = text.split(',')
                    distance_part = parts[0].split(':')[1] if ':' in parts[0] else '0'
                    quality_part = parts[1].split(':')[1] if len(parts) > 1 and ':' in parts[1] else '100'
                    measurement = {
                        'distance_mm': float(distance_part),
                        'signal_quality': int(quality_part),
                        'timestamp': time.time()
                    }
                    self.measurement_data_received.emit(measurement)
                    return
                elif 'STATUS:' in text:
                    status = text.split(':')[1] if ':' in text else text
                    self.device_status_changed.emit(f"Trạng thái: {status}")
                    # Không return; vẫn thử parse binary ở dưới nếu có
                elif 'ERROR:' in text:
                    error = text.split(':')[1] if ':' in text else text
                    self.error_occurred.emit(f"Lỗi thiết bị: {error}")
                    # Không return; vẫn thử parse binary ở dưới nếu có

            # 2) Parse dạng nhị phân theo giao thức cảm biến (gói 13 bytes bắt đầu bằng AA 00 00 22)
            self.bluetooth_buffer.extend(data)

            # Tìm và trích xuất các frame đo lường trong buffer
            HEADER_BYTE = 0xAA
            MEAS_HEADER = b'\xAA\x00\x00\x22'
            FRAME_LEN = 13

            while True:
                # Tìm vị trí header
                start_idx = self.bluetooth_buffer.find(bytes([HEADER_BYTE]))
                if start_idx == -1:
                    # Không có header -> xóa buffer rác
                    self.bluetooth_buffer.clear()
                    break

                # Nếu chưa đủ dữ liệu cho một frame, đợi thêm
                if len(self.bluetooth_buffer) - start_idx < FRAME_LEN:
                    # Giữ lại phần từ header trở đi
                    if start_idx > 0:
                        del self.bluetooth_buffer[:start_idx]
                    break

                # Có đủ bytes để kiểm tra một frame
                candidate = self.bluetooth_buffer[start_idx:start_idx + FRAME_LEN]
                if candidate.startswith(MEAS_HEADER):
                    # Parse measurement frame
                    parsed = MeskernelResponseParser.parse_measurement_response(bytes(candidate))
                    if 'error' not in parsed:
                        measurement = {
                            'distance_mm': float(parsed.get('distance_mm', 0.0)),
                            'signal_quality': int(parsed.get('signal_quality', 0)),
                            'timestamp': time.time(),
                            'raw_data': bytes(candidate)
                        }
                        self.measurement_data_received.emit(measurement)
                    # Bỏ frame này khỏi buffer và tiếp tục tìm frame kế tiếp
                    del self.bluetooth_buffer[:start_idx + FRAME_LEN]
                    continue
                else:
                    # Không khớp header đo lường, bỏ qua byte header này và tìm tiếp
                    del self.bluetooth_buffer[:start_idx + 1]
                    continue

        except Exception as e:
            self.error_occurred.emit(f"Lỗi parse dữ liệu: {e}")
    
    def is_connected(self) -> bool:
        """Kiểm tra trạng thái kết nối"""
        if self.connection_type == 'bluetooth':
            return self.bluetooth_manager and self.bluetooth_manager.is_connected()
        elif self.connection_type == 'serial':
            return self.serial_sensor is not None
        return False
    
    def get_device_info(self) -> Dict[str, Any]:
        """Lấy thông tin thiết bị"""
        return {
            'connection_type': self.connection_type,
            'laser_on': self.laser_on,
            'continuous_measuring': self.continuous_measuring,
            'measurement_rate': self.measurement_rate,
            **self.device_info
        }