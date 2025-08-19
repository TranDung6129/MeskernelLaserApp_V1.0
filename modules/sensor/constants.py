"""
Chứa các hằng số và chuỗi lệnh byte để điều khiển cảm biến Meskernel LDJ100-755.
Tất cả các lệnh được lấy từ tài liệu hướng dẫn sử dụng.
"""

# --- Header ---
HEADER = b'\xAA'

# --- Lệnh đọc (Read Commands) ---
CMD_READ_STATUS = b'\xAA\x80\x00\x00\x80'
CMD_READ_HARDWARE_VERSION = b'\xAA\x80\x00\x0A\x8A'
CMD_READ_SOFTWARE_VERSION = b'\xAA\x80\x00\x0C\x8C'
CMD_READ_SERIAL_NUMBER = b'\xAA\x80\x00\x0E\x8E'
CMD_READ_INPUT_VOLTAGE = b'\xAA\x80\x00\x06\x86'
CMD_READ_LAST_MEASUREMENT = b'\xAA\x80\x00\x22\xA2'

# --- Lệnh đo lường (Measurement Commands) ---
# Chế độ đo đơn lẻ
CMD_SINGLE_AUTO_MEASURE = b'\xAA\x00\x00\x20\x00\x01\x00\x00\x21'
CMD_SINGLE_LOW_SPEED_MEASURE = b'\xAA\x00\x00\x20\x00\x01\x00\x01\x22'
CMD_SINGLE_HIGH_SPEED_MEASURE = b'\xAA\x00\x00\x20\x00\x01\x00\x02\x23'

# Chế độ đo liên tục
CMD_CONTINUOUS_AUTO_MEASURE = b'\xAA\x00\x00\x20\x00\x01\x00\x04\x25'
CMD_CONTINUOUS_LOW_SPEED_MEASURE = b'\xAA\x00\x00\x20\x00\x01\x00\x05\x26'
CMD_CONTINUOUS_HIGH_SPEED_MEASURE = b'\xAA\x00\x00\x20\x00\x01\x00\x06\x27'

# Lệnh dừng đo liên tục
CMD_EXIT_CONTINUOUS_MODE = b'X' # Gửi ký tự 'X' (ASCII 0x58)

# --- Lệnh điều khiển Laser (Laser Control Commands) ---
CMD_TURN_LASER_ON = b'\xAA\x00\x01\xBE\x00\x01\x00\x01\xC1'
CMD_TURN_LASER_OFF = b'\xAA\x00\x01\xBE\x00\x01\x00\x00\xC0'

# --- Độ dài phản hồi mong đợi (tính bằng byte) ---
LEN_STATUS_RESPONSE = 9
LEN_VERSION_RESPONSE = 9
LEN_SERIAL_RESPONSE = 11
LEN_VOLTAGE_RESPONSE = 9
LEN_MEASUREMENT_RESPONSE = 13
LEN_LASER_CONTROL_RESPONSE = 9