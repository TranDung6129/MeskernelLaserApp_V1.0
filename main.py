"""
Main Entry Point - Điểm vào chính cho ứng dụng Laser Device Manager
Hỗ trợ cả giao diện GUI và chế độ command line
"""
import sys
import os
import argparse
from typing import Optional

# Thêm thư mục hiện tại vào Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_bluetooth_gui():
    """Chạy giao diện Bluetooth GUI"""
    try:
        from bluetooth_gui import main as gui_main
        print("Khởi động giao diện Bluetooth GUI...")
        gui_main()
    except ImportError as e:
        print(f"Lỗi import GUI: {e}")
        print("Đảm bảo đã cài đặt: pip install PyQt6 pybluez")
        sys.exit(1)
    except Exception as e:
        print(f"Lỗi chạy GUI: {e}")
        sys.exit(1)

def run_mqtt_mode():
    """Chạy chế độ MQTT/Serial"""
    try:
        import time
        import serial
        import threading
        from datetime import datetime
        from modules.sensor import MeskernelSensor
        from modules.mqtt import MQTTPublisher
        
        # Configuration
        SERIAL_PORT = '/dev/ttyUSB0'
        BAUD_RATE = 115200
        MQTT_BROKER_HOST = "192.168.102.50"
        MQTT_BROKER_PORT = 1883
        MQTT_TOPIC = "sensor/meskernel/distance"
        MQTT_PUBLISH_INTERVAL = 0.5
        
        # Shared data
        shared_data = {"latest_measurement": None}
        data_lock = threading.Lock()
        shutdown_event = threading.Event()
        
        def sensor_reading_thread(sensor: MeskernelSensor):
            """Thread đọc sensor"""
            print("Sensor reading thread started.")
            if not sensor.start_continuous_measurement():
                print("Could not enter continuous mode. Aborting.")
                shutdown_event.set()
                return

            while not shutdown_event.is_set():
                measurement = sensor.read_measurement_packet(timeout=1.0)
                if measurement:
                    with data_lock:
                        shared_data["latest_measurement"] = measurement
            
            sensor.stop_continuous_measurement()
            print("Sensor reading thread finished.")

        def mqtt_publishing_thread(publisher: MQTTPublisher):
            """Thread publish MQTT"""
            print("MQTT publishing thread started.")
            
            while not shutdown_event.is_set():
                local_measurement = None
                with data_lock:
                    if shared_data["latest_measurement"]:
                        local_measurement = shared_data["latest_measurement"].copy()

                if local_measurement:
                    payload = {
                        "distance_mm": local_measurement['distance_mm'],
                        "signal_quality": local_measurement['signal_quality'],
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    publisher.publish(MQTT_TOPIC, payload)
                    
                    dist = payload['distance_mm']
                    sq = payload['signal_quality']
                    print(f"Distance: {dist:5d} mm | Quality: {sq:3d}", end='\r')
                
                shutdown_event.wait(MQTT_PUBLISH_INTERVAL)
                
            print("\nMQTT publishing thread finished.")

        print("\n--- Starting MQTT Publishing Mode ---")
        print(f"Publishing to: '{MQTT_TOPIC}' every {MQTT_PUBLISH_INTERVAL}s")
        print("Press Ctrl+C to stop.\n")

        sensor = None
        publisher = None
        reader_thread = None
        publisher_thread = None

        try:
            sensor = MeskernelSensor(port=SERIAL_PORT, baudrate=BAUD_RATE)
            publisher = MQTTPublisher(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
            
            if not publisher.connect():
                print("MQTT connection failed. Aborting.")
                return

            shutdown_event.clear()
            
            reader_thread = threading.Thread(target=sensor_reading_thread, args=(sensor,))
            publisher_thread = threading.Thread(target=mqtt_publishing_thread, args=(publisher,))

            reader_thread.start()
            publisher_thread.start()

            while reader_thread.is_alive() and publisher_thread.is_alive():
                time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nShutdown signal received (Ctrl+C).")
        except serial.SerialException as e:
            print(f"Serial connection error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            print("Initiating shutdown...")
            shutdown_event.set()

            if reader_thread:
                reader_thread.join()
            if publisher_thread:
                publisher_thread.join()
            if publisher:
                publisher.disconnect()
            if sensor:
                sensor.close()
    
        print("MQTT mode finished.\n")
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure required modules are available")
        sys.exit(1)

def main():
    """Main function với argument parsing"""
    parser = argparse.ArgumentParser(
        description="Laser Device Manager - Quản lý thiết bị laser đo khoảng cách",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  gui     : Giao diện đồ họa Bluetooth (mặc định)
  mqtt    : Chế độ MQTT/Serial publishing
  
Examples:
  python main.py              # Chạy GUI mode
  python main.py --mode gui   # Chạy GUI mode  
  python main.py --mode mqtt  # Chạy MQTT mode
        """
    )
    
    parser.add_argument(
        '--mode', '-m',
        choices=['gui', 'mqtt'],
        default='gui',
        help='Chế độ chạy: gui (GUI Bluetooth) hoặc mqtt (MQTT/Serial)'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='Laser Device Manager v1.0.0'
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("LASER DEVICE MANAGER")
    print("=" * 50)
    
    if args.mode == 'gui':
        print("Mode: Bluetooth GUI Interface")
        run_bluetooth_gui()
    elif args.mode == 'mqtt':
        print("Mode: MQTT/Serial Publishing")
        run_mqtt_mode()
    else:
        print("Invalid mode")
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()