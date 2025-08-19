## Laser Device Manager (Bluetooth + MQTT)

Ứng dụng quản lý/giám sát cảm biến laser Meskernel (LDJ100-755) bằng Python.

- **GUI Bluetooth**: Quét, kết nối, gửi lệnh, xem dữ liệu/đồ thị realtime.
- **MQTT/Serial**: Đọc cảm biến qua Serial và publish dữ liệu lên MQTT broker.

### Yêu cầu hệ thống
- Python 3.10+ (khuyến nghị 3.11)
- Linux với BlueZ (để chạy Bluetooth). Cài đặt gói hệ thống:
  - Ubuntu/Debian: `sudo apt-get install bluetooth bluez libbluetooth-dev`

### Cài đặt
1) Tạo môi trường ảo và cài thư viện
```bash
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

2) Kiểm tra quyền Bluetooth (tuỳ hệ điều hành, có thể cần chạy bằng user thuộc group `bluetooth` hoặc `sudo`).

### Chạy ứng dụng
- Chế độ GUI (mặc định):
```bash
python main.py
# hoặc
python main.py --mode gui
```

- Chế độ MQTT/Serial:
```bash
python main.py --mode mqtt
```
Thiết lập Serial/MQTT nhanh (sửa trực tiếp trong `main.py`):
- `SERIAL_PORT` (mặc định `/dev/ttyUSB0`)
- `BAUD_RATE` (mặc định `115200`)
- `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`
- `MQTT_TOPIC`, `MQTT_PUBLISH_INTERVAL`

### Tính năng chính
- Quét và kết nối Bluetooth tới thiết bị laser
- Gửi lệnh điều khiển: bật/tắt laser, đo đơn/lặp, đọc trạng thái/phiên bản/serial/điện áp
- Hiển thị log giao tiếp, dữ liệu raw dạng hex
- Xử lý và vẽ đồ thị đo khoảng cách, chất lượng tín hiệu, tính vận tốc
- Publish dữ liệu đo qua MQTT ở chế độ Serial

### Cấu trúc thư mục
```
modules/
  bluetooth/           # Quản lý Bluetooth (scan, connect, recv/send)
  core/                # Lệnh thiết bị, controller, parser phản hồi
  mqtt/                # Publisher MQTT
  processing/          # Xử lý số liệu, tính vận tốc, thống kê
  sensor/              # Driver Serial cho cảm biến Meskernel
  ui/                  # Giao diện PyQt6 (kết nối, giao tiếp, đồ thị)
main.py                # Điểm vào, chọn chế độ gui/mqtt
bluetooth_gui.py       # Entry GUI thuận tiện
requirements.txt
```

### Phím tắt/cách dùng nhanh (GUI)
- Quét thiết bị, chọn thiết bị từ danh sách và nhấn Kết nối
- Tab "Giao Tiếp":
  - Gửi dữ liệu raw hoặc chọn lệnh thiết bị có sẵn
  - Xem log và dữ liệu nhận về
- Tab "Đồ Thị & Thống Kê":
  - Theo dõi khoảng cách, chất lượng tín hiệu, vận tốc tính toán

### Ghi chú
- Nếu cài `pybluez` lỗi trên Linux, đảm bảo đã cài `libbluetooth-dev` rồi mới `pip install pybluez`.
- Nếu không dùng Bluetooth, có thể chạy chế độ MQTT/Serial chỉ với `pyserial` + `paho-mqtt`.

### Bản quyền
© 2025 Aitogy. Dùng nội bộ hoặc theo thỏa thuận dự án.


