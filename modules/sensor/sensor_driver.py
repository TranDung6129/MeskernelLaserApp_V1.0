import serial
import time
from typing import Optional, Dict, Any
from .constants import *

class MeskernelSensor:
    """
    Driver class for communicating with the Meskernel LDJ100-755 laser distance sensor.
    """
    def __init__(self, port: str, baudrate: int = 115200, timeout: int = 2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            print(f"Successfully connected to port {self.port} at {self.baudrate} bps.")
        except serial.SerialException as e:
            print(f"Error: Could not open serial port {self.port}. {e}")
            raise

    def _send_command(self, command: bytes):
        if self.ser and self.ser.is_open:
            self.ser.write(command)
            self.ser.flush()
        else:
            raise serial.SerialException("Serial port is not open.")

    def _read_response(self, expected_length: int) -> Optional[bytes]:
        if self.ser and self.ser.is_open:
            self.ser.reset_input_buffer()
            response = self.ser.read(expected_length)
            if len(response) == expected_length:
                return response
        return None

    # --- Các phương thức hiện có không thay đổi ---
    def read_status(self) -> Optional[Dict[str, Any]]:
        self._send_command(CMD_READ_STATUS)
        response = self._read_response(LEN_STATUS_RESPONSE)
        if response and response.startswith(b'\xAA\x80\x00\x00'):
            status_code = int.from_bytes(response[6:8], 'big')
            return {"status_code": status_code}
        return None

    def read_software_version(self) -> Optional[str]:
        self._send_command(CMD_READ_SOFTWARE_VERSION)
        response = self._read_response(LEN_VERSION_RESPONSE)
        if response and response.startswith(b'\xAA\x80\x00\x0C'):
            version_hex = response[6:8].hex()
            return f"0x{version_hex.upper()}"
        return None

    def read_input_voltage(self) -> Optional[float]:
        self._send_command(CMD_READ_INPUT_VOLTAGE)
        response = self._read_response(LEN_VOLTAGE_RESPONSE)
        if response and response.startswith(b'\xAA\x80\x00\x06'):
            bcd_string = f"{response[6]:02x}{response[7]:02x}"
            voltage_mv = int(bcd_string)
            return voltage_mv / 1000.0
        return None
        
    def turn_laser(self, on: bool) -> bool:
        command = CMD_TURN_LASER_ON if on else CMD_TURN_LASER_OFF
        self._send_command(command)
        response = self._read_response(LEN_LASER_CONTROL_RESPONSE)
        if response and response.startswith(b'\xAA\x00\x01\xBE'):
            action = "ON" if on else "OFF"
            print(f"Laser control command ({action}) acknowledged by sensor.")
            return True
        print("Laser control command NOT acknowledged.")
        return False

    def single_auto_measure(self) -> Optional[Dict[str, Any]]:
        self._send_command(CMD_SINGLE_AUTO_MEASURE)
        time.sleep(0.1) 
        # For single measurement, the response IS the measurement packet
        return self.read_measurement_packet(timeout=self.timeout)

    # --- CÁC PHƯƠNG THỨC MỚI CHO CHẾ ĐỘ LIÊN TỤC ---

    def start_continuous_measurement(self) -> bool:
        """Puts the sensor into continuous auto measurement mode."""
        print("Sending command to start continuous measurement...")
        self._send_command(CMD_CONTINUOUS_AUTO_MEASURE)
        # The first response is a standard measurement packet, which acts as an acknowledgment.
        ack_packet = self.read_measurement_packet(timeout=2.0) # Give it 2s to start
        if ack_packet:
            print("Continuous measurement mode started successfully.")
            return True
        print("Failed to start continuous measurement mode.")
        return False

    def stop_continuous_measurement(self):
        """Stops the continuous measurement mode by sending 'X'."""
        print("\nSending stop command ('X')...")
        self._send_command(CMD_EXIT_CONTINUOUS_MODE)
        time.sleep(0.2) # Give sensor a moment to process the stop command
        self.ser.reset_input_buffer() # Clear any packets that might have been sent before stop
        print("Continuous measurement stopped.")

    def read_measurement_packet(self, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Reads and parses a single measurement data packet from the stream.
        This method ONLY listens and does NOT send a command first.
        """
        original_timeout = self.ser.timeout
        if timeout is not None:
            self.ser.timeout = timeout
        
        # Read until we find the start header, or timeout
        response_header = self.ser.read_until(expected=HEADER)
        
        if response_header.endswith(HEADER):
            # We found the header, now read the rest of the packet
            response_body = self.ser.read(LEN_MEASUREMENT_RESPONSE - 1)
            response = HEADER + response_body
            
            if len(response) == LEN_MEASUREMENT_RESPONSE and response.startswith(b'\xAA\x00\x00\x22'):
                distance_mm = int.from_bytes(response[6:10], 'big')
                raw_quality = int.from_bytes(response[10:12], 'big')
                # Chuẩn hoá chất lượng tín hiệu về % nếu giá trị vượt 100 (thiết bị có thể trả 0..65535)
                if raw_quality > 100:
                    # Map 0..65535 -> 0..100
                    signal_quality = max(0, min(100, round((raw_quality / 65535.0) * 100.0)))
                else:
                    signal_quality = raw_quality
                if timeout is not None:
                    self.ser.timeout = original_timeout # Restore original timeout
                return {"distance_mm": distance_mm, "signal_quality": signal_quality}
        
        if timeout is not None:
            self.ser.timeout = original_timeout # Restore original timeout
        return None

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial port connection closed.")