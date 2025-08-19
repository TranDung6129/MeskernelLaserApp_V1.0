"""
Velocity Calculator - Tính toán vận tốc từ dữ liệu khoảng cách
"""
import numpy as np
from typing import List, Optional
from collections import deque
from .data_processor import MeasurementData

class VelocityCalculator:
    """Tính toán vận tốc từ khoảng cách và thời gian"""
    
    def __init__(self, window_size: int = 5):
        """
        window_size: Số điểm dữ liệu để tính đạo hàm (smoothing)
        """
        self.window_size = window_size
        self.recent_measurements: deque = deque(maxlen=window_size)
        self.velocities: deque = deque(maxlen=1000)  # Lưu 1000 giá trị vận tốc gần nhất
        
    def add_measurement(self, measurement: MeasurementData) -> Optional[float]:
        """
        Thêm phép đo mới và tính vận tốc
        Returns: vận tốc (m/s) hoặc None nếu chưa đủ dữ liệu
        """
        self.recent_measurements.append(measurement)
        
        if len(self.recent_measurements) < 2:
            return None
            
        velocity = self._calculate_instantaneous_velocity()
        if velocity is not None:
            self.velocities.append(velocity)
            
        return velocity
    
    def _calculate_instantaneous_velocity(self) -> Optional[float]:
        """Tính vận tốc tức thời từ 2 điểm gần nhất"""
        if len(self.recent_measurements) < 2:
            return None
            
        # Lấy 2 điểm gần nhất
        p1 = self.recent_measurements[-2]
        p2 = self.recent_measurements[-1]
        
        # Tính delta
        dt = p2.timestamp - p1.timestamp
        dd = (p2.distance_mm - p1.distance_mm) / 1000.0  # Convert to meters
        
        if dt <= 0:
            return None
            
        # Vận tốc = đạo hàm khoảng cách theo thời gian
        velocity = dd / dt  # m/s
        
        return velocity
    
    def get_smoothed_velocity(self) -> Optional[float]:
        """Tính vận tốc smooth từ nhiều điểm"""
        if len(self.recent_measurements) < self.window_size:
            return self._calculate_instantaneous_velocity()
            
        # Sử dụng least squares để fit đường thẳng qua window
        measurements = list(self.recent_measurements)
        
        times = np.array([m.timestamp for m in measurements])
        distances = np.array([m.distance_mm / 1000.0 for m in measurements])  # Convert to meters
        
        # Normalize time để tránh numerical issues
        times = times - times[0]
        
        # Linear regression: distance = a*time + b
        # velocity = a (slope)
        if len(times) > 1 and np.std(times) > 0:
            coeffs = np.polyfit(times, distances, 1)
            velocity = coeffs[0]  # Slope = velocity
            return velocity
        
        return self._calculate_instantaneous_velocity()
    
    def get_velocity_array(self, count: int = 100) -> np.ndarray:
        """Lấy array vận tốc gần đây"""
        return np.array(list(self.velocities)[-count:])
    
    def get_acceleration(self) -> Optional[float]:
        """Tính gia tốc từ vận tốc"""
        if len(self.velocities) < 2:
            return None
            
        # Gia tốc = đạo hàm vận tốc
        recent_velocities = list(self.velocities)[-5:]  # Lấy 5 điểm gần nhất
        if len(recent_velocities) < 2:
            return None
            
        # Estimate time step (giả sử measurement rate ổn định)
        dt = 0.1  # Giả sử 10Hz, có thể cải thiện bằng cách track thời gian thực
        
        v1 = recent_velocities[-2]
        v2 = recent_velocities[-1]
        
        acceleration = (v2 - v1) / dt
        return acceleration
    
    def get_statistics(self) -> dict:
        """Lấy thống kê vận tốc"""
        if not self.velocities:
            return {
                'current_velocity': 0.0,
                'avg_velocity': 0.0,
                'max_velocity': 0.0,
                'min_velocity': 0.0,
                'current_acceleration': 0.0
            }
            
        velocities_array = np.array(self.velocities)
        
        return {
            'current_velocity': float(self.velocities[-1]) if self.velocities else 0.0,
            'avg_velocity': float(np.mean(velocities_array)),
            'max_velocity': float(np.max(velocities_array)),
            'min_velocity': float(np.min(velocities_array)),
            'current_acceleration': self.get_acceleration() or 0.0
        }
    
    def clear(self):
        """Xóa tất cả dữ liệu"""
        self.recent_measurements.clear()
        self.velocities.clear()
        
    @staticmethod
    def detect_motion_type(velocity: float, threshold: float = 0.01) -> str:
        """Phát hiện loại chuyển động"""
        abs_vel = abs(velocity)
        
        if abs_vel < threshold:
            return "Đứng yên"
        elif velocity > threshold:
            return "Tiến lại gần"
        elif velocity < -threshold:
            return "Lùi ra xa"
        else:
            return "Không xác định"
            
    @staticmethod
    def velocity_to_kmh(velocity_ms: float) -> float:
        """Chuyển đổi m/s sang km/h"""
        return velocity_ms * 3.6