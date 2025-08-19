"""
Commands Module - Định nghĩa các lệnh điều khiển thiết bị laser Meskernel
Dựa theo Meskernel User Manual LDJG_v1.1_en.pdf
"""
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
from ..sensor.constants import *

class CommandType(Enum):
    """Các loại lệnh điều khiển thiết bị theo manual"""
    # Laser Control Commands
    LASER_ON = "LASER_ON"
    LASER_OFF = "LASER_OFF"
    
    # Measurement Commands  
    SINGLE_AUTO_MEASURE = "SINGLE_AUTO_MEASURE"
    SINGLE_LOW_SPEED_MEASURE = "SINGLE_LOW_SPEED_MEASURE"
    SINGLE_HIGH_SPEED_MEASURE = "SINGLE_HIGH_SPEED_MEASURE"
    CONTINUOUS_AUTO_MEASURE = "CONTINUOUS_AUTO_MEASURE"
    CONTINUOUS_LOW_SPEED_MEASURE = "CONTINUOUS_LOW_SPEED_MEASURE"
    CONTINUOUS_HIGH_SPEED_MEASURE = "CONTINUOUS_HIGH_SPEED_MEASURE"
    EXIT_CONTINUOUS_MODE = "EXIT_CONTINUOUS_MODE"
    
    # Read Commands
    READ_STATUS = "READ_STATUS"
    READ_HARDWARE_VERSION = "READ_HARDWARE_VERSION"
    READ_SOFTWARE_VERSION = "READ_SOFTWARE_VERSION"
    READ_SERIAL_NUMBER = "READ_SERIAL_NUMBER"
    READ_INPUT_VOLTAGE = "READ_INPUT_VOLTAGE"
    READ_LAST_MEASUREMENT = "READ_LAST_MEASUREMENT"

@dataclass
class LaserCommand:
    """Class đại diện cho một lệnh điều khiển laser"""
    command_type: CommandType
    parameters: Optional[Dict[str, Any]] = None
    timeout: float = 5.0
    description: str = ""
    
    def to_bytes(self) -> bytes:
        """Chuyển đổi lệnh thành bytes theo protocol Meskernel"""
        cmd_map = {
            # Laser Control
            CommandType.LASER_ON: CMD_TURN_LASER_ON,
            CommandType.LASER_OFF: CMD_TURN_LASER_OFF,
            
            # Measurement Commands
            CommandType.SINGLE_AUTO_MEASURE: CMD_SINGLE_AUTO_MEASURE,
            CommandType.SINGLE_LOW_SPEED_MEASURE: CMD_SINGLE_LOW_SPEED_MEASURE,
            CommandType.SINGLE_HIGH_SPEED_MEASURE: CMD_SINGLE_HIGH_SPEED_MEASURE,
            CommandType.CONTINUOUS_AUTO_MEASURE: CMD_CONTINUOUS_AUTO_MEASURE,
            CommandType.CONTINUOUS_LOW_SPEED_MEASURE: CMD_CONTINUOUS_LOW_SPEED_MEASURE,
            CommandType.CONTINUOUS_HIGH_SPEED_MEASURE: CMD_CONTINUOUS_HIGH_SPEED_MEASURE,
            CommandType.EXIT_CONTINUOUS_MODE: CMD_EXIT_CONTINUOUS_MODE,
            
            # Read Commands
            CommandType.READ_STATUS: CMD_READ_STATUS,
            CommandType.READ_HARDWARE_VERSION: CMD_READ_HARDWARE_VERSION,
            CommandType.READ_SOFTWARE_VERSION: CMD_READ_SOFTWARE_VERSION,
            CommandType.READ_SERIAL_NUMBER: CMD_READ_SERIAL_NUMBER,
            CommandType.READ_INPUT_VOLTAGE: CMD_READ_INPUT_VOLTAGE,
            CommandType.READ_LAST_MEASUREMENT: CMD_READ_LAST_MEASUREMENT,
        }
        
        return cmd_map.get(self.command_type, b'')
    
    def get_expected_response_length(self) -> int:
        """Lấy độ dài phản hồi mong đợi"""
        length_map = {
            CommandType.READ_STATUS: LEN_STATUS_RESPONSE,
            CommandType.READ_HARDWARE_VERSION: LEN_VERSION_RESPONSE,
            CommandType.READ_SOFTWARE_VERSION: LEN_VERSION_RESPONSE,
            CommandType.READ_SERIAL_NUMBER: LEN_SERIAL_RESPONSE,
            CommandType.READ_INPUT_VOLTAGE: LEN_VOLTAGE_RESPONSE,
            CommandType.READ_LAST_MEASUREMENT: LEN_MEASUREMENT_RESPONSE,
            CommandType.LASER_ON: LEN_LASER_CONTROL_RESPONSE,
            CommandType.LASER_OFF: LEN_LASER_CONTROL_RESPONSE,
        }
        
        return length_map.get(self.command_type, 0)
    
    @classmethod
    def create_laser_on(cls) -> 'LaserCommand':
        """Tạo lệnh bật laser"""
        return cls(
            command_type=CommandType.LASER_ON,
            description="Bật laser"
        )
    
    @classmethod
    def create_laser_off(cls) -> 'LaserCommand':
        """Tạo lệnh tắt laser"""
        return cls(
            command_type=CommandType.LASER_OFF,
            description="Tắt laser"
        )
    
    @classmethod
    def create_single_auto_measure(cls) -> 'LaserCommand':
        """Tạo lệnh đo đơn tự động"""
        return cls(
            command_type=CommandType.SINGLE_AUTO_MEASURE,
            description="Đo đơn lẻ - chế độ tự động"
        )
    
    @classmethod
    def create_single_low_speed_measure(cls) -> 'LaserCommand':
        """Tạo lệnh đo đơn tốc độ thấp"""
        return cls(
            command_type=CommandType.SINGLE_LOW_SPEED_MEASURE,
            description="Đo đơn lẻ - tốc độ thấp"
        )
    
    @classmethod
    def create_single_high_speed_measure(cls) -> 'LaserCommand':
        """Tạo lệnh đo đơn tốc độ cao"""
        return cls(
            command_type=CommandType.SINGLE_HIGH_SPEED_MEASURE,
            description="Đo đơn lẻ - tốc độ cao"
        )
    
    @classmethod
    def create_continuous_auto_measure(cls) -> 'LaserCommand':
        """Tạo lệnh đo liên tục tự động"""
        return cls(
            command_type=CommandType.CONTINUOUS_AUTO_MEASURE,
            description="Đo liên tục - chế độ tự động"
        )
    
    @classmethod
    def create_continuous_low_speed_measure(cls) -> 'LaserCommand':
        """Tạo lệnh đo liên tục tốc độ thấp"""
        return cls(
            command_type=CommandType.CONTINUOUS_LOW_SPEED_MEASURE,
            description="Đo liên tục - tốc độ thấp"
        )
    
    @classmethod
    def create_continuous_high_speed_measure(cls) -> 'LaserCommand':
        """Tạo lệnh đo liên tục tốc độ cao"""
        return cls(
            command_type=CommandType.CONTINUOUS_HIGH_SPEED_MEASURE,
            description="Đo liên tục - tốc độ cao"
        )
    
    @classmethod
    def create_exit_continuous_mode(cls) -> 'LaserCommand':
        """Tạo lệnh thoát chế độ đo liên tục"""
        return cls(
            command_type=CommandType.EXIT_CONTINUOUS_MODE,
            description="Thoát chế độ đo liên tục"
        )
    
    @classmethod
    def create_read_status(cls) -> 'LaserCommand':
        """Tạo lệnh đọc trạng thái"""
        return cls(
            command_type=CommandType.READ_STATUS,
            description="Đọc trạng thái thiết bị"
        )
    
    @classmethod
    def create_read_hardware_version(cls) -> 'LaserCommand':
        """Tạo lệnh đọc phiên bản phần cứng"""
        return cls(
            command_type=CommandType.READ_HARDWARE_VERSION,
            description="Đọc phiên bản phần cứng"
        )
    
    @classmethod
    def create_read_software_version(cls) -> 'LaserCommand':
        """Tạo lệnh đọc phiên bản phần mềm"""
        return cls(
            command_type=CommandType.READ_SOFTWARE_VERSION,
            description="Đọc phiên bản phần mềm"
        )
    
    @classmethod
    def create_read_serial_number(cls) -> 'LaserCommand':
        """Tạo lệnh đọc số serial"""
        return cls(
            command_type=CommandType.READ_SERIAL_NUMBER,
            description="Đọc số serial thiết bị"
        )
    
    @classmethod
    def create_read_input_voltage(cls) -> 'LaserCommand':
        """Tạo lệnh đọc điện áp đầu vào"""
        return cls(
            command_type=CommandType.READ_INPUT_VOLTAGE,
            description="Đọc điện áp đầu vào"
        )
    
    @classmethod
    def create_read_last_measurement(cls) -> 'LaserCommand':
        """Tạo lệnh đọc phép đo cuối"""
        return cls(
            command_type=CommandType.READ_LAST_MEASUREMENT,
            description="Đọc kết quả đo cuối cùng"
        )

# (Đã loại bỏ PREDEFINED_COMMANDS do không sử dụng)