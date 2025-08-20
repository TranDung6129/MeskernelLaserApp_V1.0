"""
Response Parser - Parse phản hồi từ thiết bị Meskernel theo manual
"""
import struct
from typing import Dict, Any, Optional, Tuple
from ..sensor.constants import *

class MeskernelResponseParser:
    """Parser cho các phản hồi từ thiết bị Meskernel"""
    
    @staticmethod
    def bytes_to_hex_string(data: bytes) -> str:
        """Chuyển bytes thành hex string dễ đọc"""
        if not data:
            return ""
        return " ".join([f"{b:02X}" for b in data])
    
    @staticmethod
    def parse_status_response(data: bytes) -> Dict[str, Any]:
        """Parse phản hồi trạng thái (9 bytes)"""
        if len(data) != LEN_STATUS_RESPONSE:
            return {"error": f"Invalid status response length: {len(data)} (expected {LEN_STATUS_RESPONSE})"}
        
        try:
            # Format: AA + status_code + checksum (theo manual)
            header = data[0]
            status_code = data[1]
            # Parse các byte khác theo manual cụ thể
            
            status_info = {
                "raw_hex": MeskernelResponseParser.bytes_to_hex_string(data),
                "header": f"0x{header:02X}",
                "status_code": status_code,
                "status_text": MeskernelResponseParser._get_status_text(status_code),
                "timestamp": "now"
            }
            
            return status_info
            
        except Exception as e:
            return {"error": f"Parse error: {e}", "raw_data": data.hex()}
    
    @staticmethod
    def parse_version_response(data: bytes, is_hardware: bool = True) -> Dict[str, Any]:
        """Parse phản hồi phiên bản (9 bytes)"""
        if len(data) != LEN_VERSION_RESPONSE:
            return {"error": f"Invalid version response length: {len(data)} (expected {LEN_VERSION_RESPONSE})"}
        
        try:
            # Giả sử format: AA + version_major + version_minor + ... + checksum
            header = data[0]
            major = data[1] if len(data) > 1 else 0
            minor = data[2] if len(data) > 2 else 0
            
            version_type = "Hardware" if is_hardware else "Software"
            version_info = {
                "raw_hex": MeskernelResponseParser.bytes_to_hex_string(data),
                "header": f"0x{header:02X}",
                "version_type": version_type,
                "major": major,
                "minor": minor,
                "version_string": f"{major}.{minor}",
                "full_info": f"{version_type} Version: {major}.{minor}"
            }
            
            return version_info
            
        except Exception as e:
            return {"error": f"Parse error: {e}", "raw_data": data.hex()}
    
    @staticmethod
    def parse_serial_response(data: bytes) -> Dict[str, Any]:
        """Parse phản hồi số serial (13 bytes)"""
        if len(data) != LEN_SERIAL_RESPONSE:
            return {"error": f"Invalid serial response length: {len(data)} (expected {LEN_SERIAL_RESPONSE})"}
        
        try:
            header = data[0]
            # Payload của phản hồi bắt đầu từ byte 6 cho đến trước checksum (theo pattern các response khác)
            payload = data[6:-1] if len(data) > 7 else b""
            # Nếu payload là ASCII in được, ưu tiên hiển thị ASCII; nếu không, hiển thị dạng HEX
            is_ascii_printable = all(32 <= b <= 126 for b in payload) and len(payload) > 0
            serial_ascii = payload.decode('ascii').strip() if is_ascii_printable else ""
            serial_hex = "".join([f"{b:02X}" for b in payload])
            serial_value = serial_ascii if serial_ascii else serial_hex
            
            serial_info = {
                "raw_hex": MeskernelResponseParser.bytes_to_hex_string(data),
                "header": f"0x{header:02X}",
                "serial_number": serial_value,
                "serial_hex": serial_hex,
                "full_info": f"Serial Number: {serial_value}"
            }
            
            return serial_info
            
        except Exception as e:
            return {"error": f"Parse error: {e}", "raw_data": data.hex()}
    
    @staticmethod
    def parse_voltage_response(data: bytes) -> Dict[str, Any]:
        """Parse phản hồi điện áp (9 bytes)"""
        if len(data) != LEN_VOLTAGE_RESPONSE:
            return {"error": f"Invalid voltage response length: {len(data)} (expected {LEN_VOLTAGE_RESPONSE})"}
        
        try:
            header = data[0]
            # Thiết bị trả về BCD 2 byte tại [6], [7] biểu diễn mV (x1000)
            # Khớp với logic trong sensor_driver: ghép hai byte BCD rồi chia 1000 để ra Volt
            if len(data) >= 8:
                b1, b2 = data[6], data[7]
                nibbles = [(b1 >> 4) & 0x0F, b1 & 0x0F, (b2 >> 4) & 0x0F, b2 & 0x0F]
                if all(n <= 9 for n in nibbles):
                    voltage_mv = nibbles[0] * 1000 + nibbles[1] * 100 + nibbles[2] * 10 + nibbles[3]
                else:
                    # Fallback: không phải BCD hợp lệ, đọc big-endian số nguyên mV
                    voltage_mv = (b1 << 8) | b2
                voltage = voltage_mv / 1000.0  # V
            else:
                return {"error": "Voltage response too short"}
            
            voltage_info = {
                "raw_hex": MeskernelResponseParser.bytes_to_hex_string(data),
                "header": f"0x{header:02X}",
                "voltage_raw": voltage_mv,
                "voltage": voltage,
                "unit": "V",
                "full_info": f"Input Voltage: {voltage:.2f}V"
            }
            
            return voltage_info
            
        except Exception as e:
            return {"error": f"Parse error: {e}", "raw_data": data.hex()}
    
    @staticmethod
    def parse_measurement_response(data: bytes) -> Dict[str, Any]:
        """Parse phản hồi đo khoảng cách (13 bytes)"""
        if len(data) != LEN_MEASUREMENT_RESPONSE:
            return {"error": f"Invalid measurement response length: {len(data)} (expected {LEN_MEASUREMENT_RESPONSE})"}
        
        try:
            header = data[0]
            
            # Parse theo format ĐÚNG trong sensor_driver.py:
            # response[6:10] cho distance (4 bytes)
            # response[10:12] cho signal quality (2 bytes)
            distance_mm = int.from_bytes(data[6:10], 'big')
            raw_quality = int.from_bytes(data[10:12], 'big')
            # Chuẩn hoá chất lượng tín hiệu về phần trăm 0..100
            signal_quality = int(raw_quality)
            if raw_quality > 100:
                signal_quality = max(0, min(100, round((raw_quality / 65535.0) * 100.0)))
            
            measurement_info = {
                "raw_hex": MeskernelResponseParser.bytes_to_hex_string(data),
                "header": f"0x{header:02X}",
                "distance_mm": distance_mm,
                "signal_quality": signal_quality,
                "full_info": f"Distance: {distance_mm:.1f}mm, Quality: {signal_quality}%",
                "timestamp": "now"
            }
            
            return measurement_info
            
        except Exception as e:
            return {"error": f"Parse error: {e}", "raw_data": data.hex()}
    
    @staticmethod
    def parse_laser_control_response(data: bytes) -> Dict[str, Any]:
        """Parse phản hồi điều khiển laser (9 bytes)"""
        if len(data) != LEN_LASER_CONTROL_RESPONSE:
            return {"error": f"Invalid laser control response length: {len(data)} (expected {LEN_LASER_CONTROL_RESPONSE})"}
        
        try:
            header = data[0]
            status = data[1] if len(data) > 1 else 0
            
            laser_info = {
                "raw_hex": MeskernelResponseParser.bytes_to_hex_string(data),
                "header": f"0x{header:02X}",
                "laser_status": status,
                "laser_on": status == 1,
                "full_info": f"Laser {'ON' if status == 1 else 'OFF'} (Status: {status})"
            }
            
            return laser_info
            
        except Exception as e:
            return {"error": f"Parse error: {e}", "raw_data": data.hex()}
    
    @staticmethod
    def _get_status_text(status_code: int) -> str:
        """Chuyển status code thành text có ý nghĩa"""
        status_map = {
            0x00: "OK - Normal operation",
            0x01: "Error - Measurement failed", 
            0x02: "Error - Laser malfunction",
            0x03: "Error - Temperature too high",
            0x04: "Error - Voltage too low",
            0x05: "Warning - Signal quality low",
            0xFF: "Error - Unknown error"
        }
        
        return status_map.get(status_code, f"Unknown status: 0x{status_code:02X}")
    
    @staticmethod
    def parse_response_with_context(data: bytes, command_type: str) -> Dict[str, Any]:
        """Parse phản hồi với context từ lệnh đã gửi"""
        if not data:
            return {"error": "Empty response"}
            
        # Map command type to expected response type
        command_to_response = {
            "READ_STATUS": "status",
            "READ_HARDWARE_VERSION": "hardware_version", 
            "READ_SOFTWARE_VERSION": "software_version",
            "READ_SERIAL_NUMBER": "serial",
            "READ_INPUT_VOLTAGE": "voltage",
            "READ_LAST_MEASUREMENT": "measurement",
            "SINGLE_AUTO_MEASURE": "measurement",
            "SINGLE_LOW_SPEED_MEASURE": "measurement", 
            "SINGLE_HIGH_SPEED_MEASURE": "measurement",
            "LASER_ON": "laser_control",
            "LASER_OFF": "laser_control"
        }
        
        expected_type = command_to_response.get(command_type, "unknown")
        return MeskernelResponseParser.parse_any_response(data, expected_type)
    
    @staticmethod
    def parse_any_response(data: bytes, expected_type: str = "unknown") -> Dict[str, Any]:
        """Parse bất kỳ phản hồi nào dựa trên độ dài và loại mong đợi"""
        if not data:
            return {"error": "Empty response"}
        
        length = len(data)
        
        # Tự động detect type dựa trên length và header
        if expected_type == "unknown":
            header = data[0] if data else 0
            
            if length == LEN_STATUS_RESPONSE:
                expected_type = "status"
            elif length == LEN_VERSION_RESPONSE:
                expected_type = "version" 
            elif length == LEN_VOLTAGE_RESPONSE:
                expected_type = "voltage"
            elif length == LEN_MEASUREMENT_RESPONSE or length == LEN_SERIAL_RESPONSE:
                # 13 bytes có thể là measurement hoặc serial -> phân biệt theo tiền tố header
                if data.startswith(b'\xAA\x00\x00\x22'):
                    expected_type = "measurement"
                elif data.startswith(b'\xAA\x80\x00\x0E'):
                    expected_type = "serial"
                else:
                    # Không rõ, vẫn ưu tiên measurement nhưng sẽ ghi rõ type unknown nếu parse fail
                    expected_type = "measurement"
            elif length == LEN_LASER_CONTROL_RESPONSE:
                expected_type = "laser_control"
        
        # Parse theo type
        if expected_type == "status":
            return MeskernelResponseParser.parse_status_response(data)
        elif expected_type == "version":
            return MeskernelResponseParser.parse_version_response(data)
        elif expected_type == "hardware_version":
            return MeskernelResponseParser.parse_version_response(data, True)
        elif expected_type == "software_version":
            return MeskernelResponseParser.parse_version_response(data, False)
        elif expected_type == "serial":
            return MeskernelResponseParser.parse_serial_response(data)
        elif expected_type == "voltage":
            return MeskernelResponseParser.parse_voltage_response(data)
        elif expected_type == "measurement":
            return MeskernelResponseParser.parse_measurement_response(data)
        elif expected_type == "laser_control":
            return MeskernelResponseParser.parse_laser_control_response(data)
        else:
            # Default: trả về hex và thông tin cơ bản
            return {
                "raw_hex": MeskernelResponseParser.bytes_to_hex_string(data),
                "length": length,
                "type": "unknown",
                "full_info": f"Unknown response ({length} bytes): {MeskernelResponseParser.bytes_to_hex_string(data)}"
            }