"""
State Detector - Nhận diện trạng thái Khoan/Dừng dựa trên vận tốc với hysteresis
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal


DrillState = Literal["Khoan", "Dừng", "Rút cần"]


@dataclass
class StateDetectorConfig:
    velocity_threshold: float = 0.005  # m/s
    min_duration_below_s: float = 3.0  # phải dưới ngưỡng liên tục >= 3s để chuyển sang Dừng
    min_duration_above_s: float = 1.0  # phải trên ngưỡng liên tục >= 1s để chuyển sang Khoan/Rút


class StateDetector:
    """Hysteresis-based state detector for drilling vs stopped."""

    def __init__(self, config: Optional[StateDetectorConfig] = None):
        self.config = config or StateDetectorConfig()
        self.current_state: DrillState = "Dừng"
        self._last_state_change_ts: Optional[float] = None
        self._last_below_start_ts: Optional[float] = None
        self._last_above_pos_start_ts: Optional[float] = None
        self._last_above_neg_start_ts: Optional[float] = None

        # Accumulated durations
        self.total_time_drilling_s: float = 0.0
        self.total_time_stopped_s: float = 0.0
        self._last_update_ts: Optional[float] = None

    def update(self, velocity_ms: float, timestamp_s: float) -> DrillState:
        """Update detector with a new velocity sample at given timestamp."""
        # Update accumulators based on time elapsed in the current state
        if self._last_update_ts is not None:
            dt = max(0.0, timestamp_s - self._last_update_ts)
            if self.current_state == "Khoan":
                self.total_time_drilling_s += dt
            else:
                self.total_time_stopped_s += dt
        self._last_update_ts = timestamp_s

        abs_v = abs(velocity_ms)
        thr = self.config.velocity_threshold

        # Track continuous durations relative to threshold
        if abs_v < thr:
            # Below threshold
            if self._last_below_start_ts is None:
                self._last_below_start_ts = timestamp_s
            # reset above streak
            self._last_above_pos_start_ts = None
            self._last_above_neg_start_ts = None
        else:
            # Above threshold
            if velocity_ms >= thr:
                if self._last_above_pos_start_ts is None:
                    self._last_above_pos_start_ts = timestamp_s
                self._last_above_neg_start_ts = None
            elif velocity_ms <= -thr:
                if self._last_above_neg_start_ts is None:
                    self._last_above_neg_start_ts = timestamp_s
                self._last_above_pos_start_ts = None
            # reset below streak
            self._last_below_start_ts = None

        # Hysteresis: require sustained durations to flip state
        if self.current_state == "Khoan":
            # Switch to Dừng if sustained below thr
            if self._last_below_start_ts is not None:
                below_duration = timestamp_s - self._last_below_start_ts
                if below_duration >= self.config.min_duration_below_s:
                    self._change_state("Dừng", timestamp_s)
            # Or switch to Rút cần if sustained negative above thr
            elif self._last_above_neg_start_ts is not None:
                above_neg_duration = timestamp_s - self._last_above_neg_start_ts
                if above_neg_duration >= self.config.min_duration_above_s:
                    self._change_state("Rút cần", timestamp_s)
        elif self.current_state == "Rút cần":
            if self._last_below_start_ts is not None:
                below_duration = timestamp_s - self._last_below_start_ts
                if below_duration >= self.config.min_duration_below_s:
                    self._change_state("Dừng", timestamp_s)
            elif self._last_above_pos_start_ts is not None:
                above_pos_duration = timestamp_s - self._last_above_pos_start_ts
                if above_pos_duration >= self.config.min_duration_above_s:
                    self._change_state("Khoan", timestamp_s)
        else:  # current_state == "Dừng"
            if self._last_above_pos_start_ts is not None:
                above_pos_duration = timestamp_s - self._last_above_pos_start_ts
                if above_pos_duration >= self.config.min_duration_above_s:
                    self._change_state("Khoan", timestamp_s)
            elif self._last_above_neg_start_ts is not None:
                above_neg_duration = timestamp_s - self._last_above_neg_start_ts
                if above_neg_duration >= self.config.min_duration_above_s:
                    self._change_state("Rút cần", timestamp_s)

        return self.current_state

    def _change_state(self, new_state: DrillState, timestamp_s: float) -> None:
        self.current_state = new_state
        self._last_state_change_ts = timestamp_s
        # Reset streaks on state change
        self._last_below_start_ts = None
        self._last_above_pos_start_ts = None
        self._last_above_neg_start_ts = None

    def get_efficiency_percent(self) -> float:
        total = self.total_time_drilling_s + self.total_time_stopped_s
        if total <= 0.0:
            return 0.0
        return (self.total_time_drilling_s / total) * 100.0

    def reset(self) -> None:
        self.current_state = "Dừng"
        self._last_state_change_ts = None
        self._last_below_start_ts = None
        self._last_above_pos_start_ts = None
        self._last_above_neg_start_ts = None
        self.total_time_drilling_s = 0.0
        self.total_time_stopped_s = 0.0
        self._last_update_ts = None

