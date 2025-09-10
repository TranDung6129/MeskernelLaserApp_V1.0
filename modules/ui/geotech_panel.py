"""
Geotech Panel - Phân tích chuyên sâu (Khoan địa chất)
Hiển thị đồ thị lớn: Vận tốc (trục X) theo Độ sâu (trục Y)
Kèm form nhập thông tin hố khoan và lưu dữ liệu theo từng hố khoan.
"""
from __future__ import annotations

import os
import time
from typing import Dict, Any, List, Optional

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont, QPen, QColor
from PyQt6.QtWidgets import (
	QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
	QLineEdit, QTextEdit, QPushButton, QCheckBox, QLabel, QSplitter,
	QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, QHeaderView, QAbstractItemView, QStyledItemDelegate, QSizePolicy
)
class ColumnSeparatorDelegate(QStyledItemDelegate):
	"""Vẽ đường kẻ phân cách dọc ở bên phải cột 0 để ngăn cách hai cột."""

	def __init__(self, parent=None, color: QColor | None = None, thickness: int = 1):
		super().__init__(parent)
		self._color = color or QColor(208, 208, 208)
		self._thickness = thickness

	def paint(self, painter, option, index):  # type: ignore[override]
		# Vẽ nội dung mặc định
		super().paint(painter, option, index)
		# Chỉ vẽ separator cho cột 0
		if index.column() == 0:
			painter.save()
			painter.setPen(QPen(self._color, self._thickness))
			x = option.rect.right()
			painter.drawLine(x, option.rect.top(), x, option.rect.bottom())
			painter.restore()


import pyqtgraph as pg # type: ignore[attr-defined]
import numpy as np


class GeotechPanel(QWidget):
	"""Panel phân tích khoan địa chất.

	- Đồ thị: Vận tốc (m/s) theo Độ sâu (m)
	- Bảng thông số: độ sâu hiện tại/tối đa, vận tốc hiện tại/trung bình/tối đa/tối thiểu, số mẫu
	- Form: thông tin hố khoan và lưu dữ liệu theo hố khoan
	"""

	def __init__(self):
		super().__init__()
		self._init_state()
		self._setup_ui()

	def _init_state(self):
		# Dữ liệu theo hố khoan hiện tại
		self.depth_series_m: List[float] = []
		self.velocity_series_ms: List[float] = []
		self.quality_series: List[int] = []
		self.time_series: List[float] = []
		self.state_series: List[str] = []

		self._velocity_threshold: float = 0.005

		# Giới hạn và throttle để giảm lag UI
		self.max_points: int = 1500
		self.update_interval_s: float = 0.2
		self._last_redraw_ts: float = 0.0
		self.hist_update_interval_s: float = 1.0
		self._hist_last_update_ts: float = 0.0

		# Danh sách các cửa sổ popout đang mở để cập nhật realtime
		self.popout_windows: List[Dict[str, Any]] = []
		
		# Đơn vị đo
		self.depth_unit = "m"  # m, mm, cm
		self.velocity_unit = "m/s"  # m/s, mm/s, cm/s

		self.is_recording: bool = False
		self.current_borehole: Dict[str, Any] = {
			"name": "",
			"location": "",
			"operator": "",
			"notes": "",
			"started_at": None
		}

	def _setup_ui(self):
		layout = QVBoxLayout(self)

		# Splitter trái-phải: trái là chart, phải là form + stats
		main_splitter = QSplitter(Qt.Orientation.Horizontal)
		main_splitter.setChildrenCollapsible(False)
		main_splitter.setHandleWidth(8)

		# Khu vực đồ thị
		chart_container = QWidget()
		chart_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		chart_layout = QVBoxLayout(chart_container)
		# Giảm margins/spacing để tăng không gian biểu đồ
		chart_layout.setContentsMargins(8, 8, 8, 8)
		chart_layout.setSpacing(8)

		self.plot_widget = pg.PlotWidget()
		self.plot_widget.setBackground('w')
		self.plot_widget.showGrid(x=True, y=True)
		self.plot_widget.setLabel('left', 'Độ sâu', units='m', angle=0)
		self.plot_widget.setLabel('bottom', 'Vận tốc', units='m/s')
		self.plot_widget.setTitle('Vận tốc theo độ sâu (Khoan địa chất)', color='k', size='12pt')
		# Thiết lập size policy và constraints cho plot chính
		self.plot_widget.setMinimumHeight(300)
		self.plot_widget.setMaximumHeight(600)  # Giới hạn chiều cao tối đa trên màn hình lớn
		self.plot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
		try:
			# Quay ngược đồ thị: để độ sâu tăng dần theo trục Y hướng xuống dưới (chuẩn khoan)
			self.plot_widget.getViewBox().invertY(True)
			axis_left = self.plot_widget.getAxis('left')
			axis_bottom = self.plot_widget.getAxis('bottom')
			small_font = QFont('Arial', 9)
			axis_left.setStyle(tickFont=small_font, autoExpandTextSpace=True, tickTextOffset=12)
			axis_bottom.setStyle(tickFont=small_font, autoExpandTextSpace=True, tickTextOffset=12)
			axis_left.setWidth(120)
			axis_bottom.setHeight(48)
		except Exception:
			pass

		# Đường cong (line) và scatter theo trạng thái
		self.line_drill = self.plot_widget.plot([], [], pen=pg.mkPen(color=(0, 150, 0), width=2))
		self.line_stop = self.plot_widget.plot([], [], pen=pg.mkPen(color=(200, 0, 0), width=2))
		self.line_retract = self.plot_widget.plot([], [], pen=pg.mkPen(color=(240, 160, 0), width=2))
		self.scatter_drill = pg.ScatterPlotItem(size=6, pen=pg.mkPen(None), brush=pg.mkBrush(50, 180, 50, 200))
		self.scatter_stop = pg.ScatterPlotItem(size=6, pen=pg.mkPen(None), brush=pg.mkBrush(220, 60, 60, 200))
		self.scatter_retract = pg.ScatterPlotItem(size=6, pen=pg.mkPen(None), brush=pg.mkBrush(240, 160, 0, 200))
		self.plot_widget.addItem(self.scatter_drill)
		self.plot_widget.addItem(self.scatter_stop)
		self.plot_widget.addItem(self.scatter_retract)
		# Legend cho trạng thái
		try:
			legend = self.plot_widget.addLegend()
			legend.addItem(self.scatter_drill, 'Khoan')
			legend.addItem(self.scatter_stop, 'Dừng')
			legend.addItem(self.scatter_retract, 'Rút cần')
		except Exception:
			pass

		# Thanh công cụ đơn giản
		toolbar = QHBoxLayout()
		self.cb_autoscale = QCheckBox("Auto scale")
		self.cb_autoscale.setChecked(True)
		self.btn_clear_chart = QPushButton("Xóa biểu đồ")
		self.btn_clear_chart.clicked.connect(self._clear_chart)
		
		# Đơn vị đo
		from PyQt6.QtWidgets import QComboBox
		self.lbl_depth_unit = QLabel("Độ sâu:")
		self.combo_depth_unit = QComboBox()
		self.combo_depth_unit.addItems(["m", "cm", "mm"])
		self.combo_depth_unit.setCurrentText(self.depth_unit)
		self.combo_depth_unit.currentTextChanged.connect(self._on_depth_unit_changed)
		
		self.lbl_velocity_unit = QLabel("Vận tốc:")
		self.combo_velocity_unit = QComboBox()
		self.combo_velocity_unit.addItems(["m/s", "cm/s", "mm/s"])
		self.combo_velocity_unit.setCurrentText(self.velocity_unit)
		self.combo_velocity_unit.currentTextChanged.connect(self._on_velocity_unit_changed)
		
		self.lbl_current = QLabel("Độ sâu: -- m | Vận tốc: -- m/s")
		self.lbl_current.setFont(QFont('Arial', 11, QFont.Weight.Bold))
		toolbar.addWidget(self.lbl_current)
		toolbar.addStretch()
		toolbar.addWidget(self.lbl_depth_unit)
		toolbar.addWidget(self.combo_depth_unit)
		toolbar.addWidget(self.lbl_velocity_unit)
		toolbar.addWidget(self.combo_velocity_unit)
		toolbar.addWidget(self.cb_autoscale)
		toolbar.addWidget(self.btn_clear_chart)

		chart_layout.addLayout(toolbar)
		chart_layout.addWidget(self.plot_widget, stretch=3)  # Plot chính chiếm 3/5 không gian
		
		# Double-click để mở cửa sổ riêng
		self.plot_widget.mouseDoubleClickEvent = lambda event: self._popout_plot(self.plot_widget, "Velocity-Depth")

		# Thêm cụm đồ thị phụ: Độ sâu - thời gian, Vận tốc - thời gian, và histogram
		self.subplots_splitter = QSplitter(Qt.Orientation.Horizontal)
		self.subplots_splitter.setMinimumHeight(250)
		self.subplots_splitter.setMaximumHeight(400)  # Tăng range cho màn hình lớn
		self.subplots_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
		# Depth vs Time
		self.depth_time_plot = pg.PlotWidget()
		self.depth_time_plot.setBackground('w')
		self.depth_time_plot.showGrid(x=True, y=True)
		self.depth_time_plot.setLabel('left', 'Độ sâu', units='m')
		self.depth_time_plot.setLabel('bottom', 'Thời gian', units='s')
		self.depth_time_plot.setTitle('Độ sâu theo thời gian')
		# Thiết lập size policy
		self.depth_time_plot.setMinimumWidth(200)
		self.depth_time_plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		self.depth_time_curve_drill = self.depth_time_plot.plot([], [], pen=pg.mkPen(color=(0, 150, 0), width=2))
		self.depth_time_curve_stop = self.depth_time_plot.plot([], [], pen=pg.mkPen(color=(200, 0, 0), width=2))
		self.depth_time_curve_retract = self.depth_time_plot.plot([], [], pen=pg.mkPen(color=(240, 160, 0), width=2))
		try:
			legend_dt = self.depth_time_plot.addLegend()
			legend_dt.addItem(self.depth_time_curve_drill, 'Khoan')
			legend_dt.addItem(self.depth_time_curve_stop, 'Dừng')
			legend_dt.addItem(self.depth_time_curve_retract, 'Rút cần')
		except Exception:
			pass
		try:
			self.depth_time_plot.getViewBox().invertY(True)
		except Exception:
			pass
		self.subplots_splitter.addWidget(self.depth_time_plot)
		# Double-click để mở cửa sổ riêng
		self.depth_time_plot.mouseDoubleClickEvent = lambda event: self._popout_plot(self.depth_time_plot, "Depth-Time")

		# Velocity vs Time
		self.velocity_time_plot = pg.PlotWidget()
		self.velocity_time_plot.setBackground('w')
		self.velocity_time_plot.showGrid(x=True, y=True)
		self.velocity_time_plot.setLabel('left', 'Vận tốc', units='m/s')
		self.velocity_time_plot.setLabel('bottom', 'Thời gian', units='s')
		self.velocity_time_plot.setTitle('Vận tốc theo thời gian')
		# Thiết lập size policy
		self.velocity_time_plot.setMinimumWidth(200)
		self.velocity_time_plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		self.velocity_time_curve_drill = self.velocity_time_plot.plot([], [], pen=pg.mkPen(color=(0, 150, 0), width=2))
		self.velocity_time_curve_stop = self.velocity_time_plot.plot([], [], pen=pg.mkPen(color=(200, 0, 0), width=2))
		self.velocity_time_curve_retract = self.velocity_time_plot.plot([], [], pen=pg.mkPen(color=(240, 160, 0), width=2))
		try:
			legend_vt = self.velocity_time_plot.addLegend()
			legend_vt.addItem(self.velocity_time_curve_drill, 'Khoan')
			legend_vt.addItem(self.velocity_time_curve_stop, 'Dừng')
			legend_vt.addItem(self.velocity_time_curve_retract, 'Rút cần')
		except Exception:
			pass
		# Threshold lines
		self.vel_thr_pos = pg.InfiniteLine(angle=0, pos=self._velocity_threshold, pen=pg.mkPen(color=(0, 160, 0), style=Qt.PenStyle.DashLine))
		self.vel_thr_neg = pg.InfiniteLine(angle=0, pos=-self._velocity_threshold, pen=pg.mkPen(color=(200, 0, 0), style=Qt.PenStyle.DashLine))
		self.velocity_time_plot.addItem(self.vel_thr_pos)
		self.velocity_time_plot.addItem(self.vel_thr_neg)
		self.subplots_splitter.addWidget(self.velocity_time_plot)
		# Double-click để mở cửa sổ riêng
		self.velocity_time_plot.mouseDoubleClickEvent = lambda event: self._popout_plot(self.velocity_time_plot, "Velocity-Time")

		# Velocity histogram
		self.hist_plot = pg.PlotWidget()
		self.hist_plot.setBackground('w')
		self.hist_plot.showGrid(x=True, y=True)
		self.hist_plot.setLabel('left', 'Tần suất')
		self.hist_plot.setLabel('bottom', 'Vận tốc', units='m/s')
		self.hist_plot.setTitle('Phân bố vận tốc')
		# Thiết lập size policy
		self.hist_plot.setMinimumWidth(200)
		self.hist_plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		self._hist_bar = None
		self.subplots_splitter.addWidget(self.hist_plot)
		# Double-click để mở cửa sổ riêng
		self.hist_plot.mouseDoubleClickEvent = lambda event: self._popout_plot(self.hist_plot, "Velocity-Histogram")

		chart_layout.addWidget(self.subplots_splitter, stretch=2)  # Subplot chiếm 2/5 không gian
		
		# Thiết lập tỷ lệ cho subplots_splitter (các đồ thị phụ có kích thước bằng nhau)
		self.subplots_splitter.setSizes([400, 400, 400])
		self.subplots_splitter.setStretchFactor(0, 1)  # Depth-Time
		self.subplots_splitter.setStretchFactor(1, 1)  # Velocity-Time
		self.subplots_splitter.setStretchFactor(2, 1)  # Histogram
		
		main_splitter.addWidget(chart_container)

		# Khu vực phải: form + stats
		right_container = QWidget()
		# Thu nhỏ panel bên phải bằng cách giới hạn độ rộng
		right_container.setMinimumWidth(340)
		right_container.setMaximumWidth(560)
		right_layout = QVBoxLayout(right_container)
		right_layout.setContentsMargins(8, 8, 8, 8)
		right_layout.setSpacing(8)

		# Form thông tin hố khoan
		form_group = QGroupBox("Hố khoan")
		form_layout = QFormLayout(form_group)
		self.edt_name = QLineEdit()
		self.edt_location = QLineEdit()
		self.edt_operator = QLineEdit()
		self.txt_notes = QTextEdit()
		self.txt_notes.setFixedHeight(80)

		form_layout.addRow("Tên hố khoan", self.edt_name)
		form_layout.addRow("Vị trí", self.edt_location)
		form_layout.addRow("Người vận hành", self.edt_operator)
		form_layout.addRow("Ghi chú", self.txt_notes)

		buttons_layout = QHBoxLayout()
		self.cb_record = QCheckBox("Ghi dữ liệu")
		self.btn_start = QPushButton("Bắt đầu phiên mới")
		self.btn_save = QPushButton("Lưu CSV")
		self.btn_start.clicked.connect(self._start_new_session)
		self.btn_save.clicked.connect(self._save_csv)
		self.cb_record.stateChanged.connect(self._toggle_recording)
		buttons_layout.addWidget(self.cb_record)
		buttons_layout.addStretch()
		buttons_layout.addWidget(self.btn_start)
		buttons_layout.addWidget(self.btn_save)

		right_layout.addWidget(form_group)
		right_layout.addLayout(buttons_layout)

		# Bảng thông số
		stats_group = QGroupBox("Thông số khoan")
		try:
			stats_group.setAlignment(Qt.AlignmentFlag.AlignHCenter)
		except Exception:
			pass
		stats_layout = QVBoxLayout(stats_group)
		self.stats_table = QTableWidget()
		self.stats_table.setColumnCount(2)
		self.stats_table.setHorizontalHeaderLabels(["Thông số", "Giá trị"])
		self.stats_rows = {
			"current_depth": "Độ sâu hiện tại (m)",
			"max_depth": "Độ sâu tối đa (m)",
			"current_velocity": "Vận tốc hiện tại (m/s)",
			"avg_velocity": "Vận tốc trung bình (m/s)",
			"min_velocity": "Vận tốc nhỏ nhất (m/s)",
			"max_velocity": "Vận tốc lớn nhất (m/s)",
			"state": "Trạng thái",
			"time_drilling_s": "Tổng thời gian khoan (s)",
			"time_stopped_s": "Tổng thời gian dừng (s)",
			"efficiency_percent": "Hiệu suất (%)",
			"velocity_threshold": "Ngưỡng vận tốc (m/s)",
			"total_samples": "Số mẫu (phiên hiện tại)"
		}
		self.stats_table.setRowCount(len(self.stats_rows))
		for i, (key, label) in enumerate(self.stats_rows.items()):
			name_item = QTableWidgetItem(label)
			value_item = QTableWidgetItem("--")
			# Căn chỉnh để cân đối hiển thị
			value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
			name_item.setToolTip(label)
			value_item.setToolTip("--")
			self.stats_table.setItem(i, 0, name_item)
			self.stats_table.setItem(i, 1, value_item)

		# Cân đối bảng: cột tên có thể kéo, cột giá trị giãn hết còn lại
		header = self.stats_table.horizontalHeader()
		header.setStretchLastSection(True)
		header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
		header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
		try:
			header.resizeSection(0, 180)
			# Tránh elide tiêu đề cột
			header.setTextElideMode(Qt.TextElideMode.ElideNone)
			header.setMinimumSectionSize(120)
			header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
		except Exception:
			pass
		self.stats_table.verticalHeader().setVisible(False)
		self.stats_table.setAlternatingRowColors(True)
		self.stats_table.setShowGrid(False)
		self.stats_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
		self.stats_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
		self.stats_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
		self.stats_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
		self.stats_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
		self.stats_table.setWordWrap(True)
		# Gắn delegate để vẽ đường phân cách giữa hai cột
		self.stats_table.setItemDelegate(ColumnSeparatorDelegate(self.stats_table))
		# Tự động giãn hàng theo nội dung để hiển thị đẹp trên màn hình ban đầu
		try:
			self.stats_table.resizeRowsToContents()
			total_h = header.height()
			for i in range(self.stats_table.rowCount()):
				total_h += self.stats_table.rowHeight(i)
			self.stats_table.setFixedHeight(total_h + 6)
		except Exception:
			pass
		stats_layout.addWidget(self.stats_table)

		right_layout.addWidget(stats_group)
		right_layout.addStretch()

		main_splitter.addWidget(right_container)
		# Mở rộng khung đồ thị nhưng cho phép panel phải rộng hơn để bảng cân đối
		# Điều chỉnh cho màn hình lớn: chart chiếm nhiều không gian hơn
		main_splitter.setSizes([1200, 400])
		main_splitter.setStretchFactor(0, 3)  # Chart container
		main_splitter.setStretchFactor(1, 1)  # Right container

		layout.addWidget(main_splitter)

	@pyqtSlot(dict)
	def on_new_processed_data(self, data: Dict[str, Any]):
		"""Nhận dữ liệu từ DataProcessor và cập nhật biểu đồ + bảng."""
		try:
			depth_m: Optional[float] = None
			velocity_ms: Optional[float] = None
			quality: Optional[int] = None
			state: Optional[str] = None
			ts: float = data.get('timestamp', time.time())

			if 'distance_m' in data:
				depth_m = float(data['distance_m'])
			elif 'distance_mm' in data:
				depth_m = float(data['distance_mm']) / 1000.0

			if 'velocity_ms' in data:
				velocity_ms = float(data['velocity_ms'])
			if 'signal_quality' in data:
				quality = int(data['signal_quality'])
			if 'state' in data:
				state = str(data['state'])
			if 'velocity_threshold' in data:
				try:
					self._velocity_threshold = float(data['velocity_threshold'])
					self.vel_thr_pos.setValue(self._velocity_threshold)
					self.vel_thr_neg.setValue(-self._velocity_threshold)
				except Exception:
					pass

			if depth_m is None or velocity_ms is None:
				return

			# Cập nhật nhãn nhanh với đơn vị
			converted_depth = self._convert_depth_value(depth_m)
			converted_velocity = self._convert_velocity_value(velocity_ms)
			self.lbl_current.setText(f"Độ sâu: {converted_depth:.3f} {self.depth_unit} | Vận tốc: {converted_velocity:.3f} {self.velocity_unit}")

			if not self.is_recording:
				# Vẫn cập nhật đồ thị để xem realtime, nhưng không lưu series nếu không ghi
				self._update_plot_preview(depth_m, velocity_ms, state)
				return

			# Ghi dữ liệu vào series
			self.depth_series_m.append(depth_m)
			self.velocity_series_ms.append(velocity_ms)
			self.time_series.append(ts)
			self.quality_series.append(quality if quality is not None else 0)
			self.state_series.append(state if state is not None else "")

			# Giới hạn số điểm để tránh lag UI
			if len(self.depth_series_m) > self.max_points:
				self.depth_series_m = self.depth_series_m[-self.max_points:]
				self.velocity_series_ms = self.velocity_series_ms[-self.max_points:]
				self.time_series = self.time_series[-self.max_points:]
				self.quality_series = self.quality_series[-self.max_points:]
				self.state_series = self.state_series[-self.max_points:]

			# Throttle vẽ
			should_update_popout = False
			if ts - self._last_redraw_ts >= self.update_interval_s:
				self._refresh_plot()
				self._refresh_time_plots()
				self._refresh_stats()
				self._last_redraw_ts = ts
				should_update_popout = True
			# Histogram cập nhật thưa hơn
			if ts - self._hist_last_update_ts >= self.hist_update_interval_s:
				self._refresh_histogram()
				self._hist_last_update_ts = ts
				should_update_popout = True
			
			# Cập nhật popout windows nếu có thay đổi
			if should_update_popout:
				self._update_popout_windows()
		except Exception as e:
			print(f"GeotechPanel update error: {e}")

	def _update_plot_preview(self, depth_m: float, velocity_ms: float, state: Optional[str]):
		"""Hiển thị nhanh điểm gần nhất khi không ghi dữ liệu."""
		# Vẽ preview theo trạng thái
		stl = (state or "").lower()
		if stl.startswith('khoan'):
			self.line_drill.setData([velocity_ms], [depth_m])
			self.line_stop.setData([], [])
			self.line_retract.setData([], [])
			self.scatter_drill.setData([velocity_ms], [depth_m])
			self.scatter_stop.setData([], [])
			self.scatter_retract.setData([], [])
		elif ('rút' in stl) or ('rut' in stl):
			self.line_retract.setData([velocity_ms], [depth_m])
			self.line_drill.setData([], [])
			self.line_stop.setData([], [])
			self.scatter_retract.setData([velocity_ms], [depth_m])
			self.scatter_drill.setData([], [])
			self.scatter_stop.setData([], [])
		else:
			self.line_stop.setData([velocity_ms], [depth_m])
			self.line_drill.setData([], [])
			self.line_retract.setData([], [])
			self.scatter_stop.setData([velocity_ms], [depth_m])
			self.scatter_drill.setData([], [])
			self.scatter_retract.setData([], [])
		if self.cb_autoscale.isChecked():
			self.plot_widget.enableAutoRange()

	def _refresh_plot(self):
		if not self.depth_series_m or not self.velocity_series_ms:
			self.line_drill.setData([], [])
			self.line_stop.setData([], [])
			self.line_retract.setData([], [])
			self.scatter_drill.setData([], [])
			self.scatter_stop.setData([], [])
			self.scatter_retract.setData([], [])
			return
		# Tách dữ liệu theo trạng thái và chuyển đổi đơn vị
		vel_drill, dep_drill = [], []
		vel_stop, dep_stop = [], []
		vel_retract, dep_retract = [], []
		for i in range(len(self.depth_series_m)):
			st = self.state_series[i] if i < len(self.state_series) else ""
			stl = st.lower()
			converted_vel = self._convert_velocity_value(self.velocity_series_ms[i])
			converted_dep = self._convert_depth_value(self.depth_series_m[i])
			if stl.startswith('khoan'):
				vel_drill.append(converted_vel)
				dep_drill.append(converted_dep)
			elif 'rút' in stl or 'rut' in stl:
				vel_retract.append(converted_vel)
				dep_retract.append(converted_dep)
			else:
				vel_stop.append(converted_vel)
				dep_stop.append(converted_dep)
		# Cập nhật line/point theo từng trạng thái
		self.line_drill.setData(vel_drill, dep_drill)
		self.line_stop.setData(vel_stop, dep_stop)
		self.line_retract.setData(vel_retract, dep_retract)
		self.scatter_drill.setData(vel_drill, dep_drill)
		self.scatter_stop.setData(vel_stop, dep_stop)
		self.scatter_retract.setData(vel_retract, dep_retract)
		if self.cb_autoscale.isChecked():
			self.plot_widget.enableAutoRange()

	def _refresh_time_plots(self):
		if not self.time_series or not self.depth_series_m or not self.velocity_series_ms:
			self.depth_time_curve_drill.setData([], [])
			self.depth_time_curve_stop.setData([], [])
			self.depth_time_curve_retract.setData([], [])
			self.velocity_time_curve_drill.setData([], [])
			self.velocity_time_curve_stop.setData([], [])
			self.velocity_time_curve_retract.setData([], [])
			return
		# Thời gian tương đối theo mốc phiên
		t0 = self.time_series[0]
		times = [t - t0 for t in self.time_series]
		t_drill, d_drill, v_drill = [], [], []
		t_stop, d_stop, v_stop = [], [], []
		t_retract, d_retract, v_retract = [], [], []
		for i in range(len(times)):
			st = self.state_series[i] if i < len(self.state_series) else ""
			stl = st.lower()
			converted_dep = self._convert_depth_value(self.depth_series_m[i])
			converted_vel = self._convert_velocity_value(self.velocity_series_ms[i])
			if stl.startswith('khoan'):
				t_drill.append(times[i])
				d_drill.append(converted_dep)
				v_drill.append(converted_vel)
			elif 'rút' in stl or 'rut' in stl:
				t_retract.append(times[i])
				d_retract.append(converted_dep)
				v_retract.append(converted_vel)
			else:
				t_stop.append(times[i])
				d_stop.append(converted_dep)
				v_stop.append(converted_vel)
		self.depth_time_curve_drill.setData(t_drill, d_drill)
		self.depth_time_curve_stop.setData(t_stop, d_stop)
		self.depth_time_curve_retract.setData(t_retract, d_retract)
		self.velocity_time_curve_drill.setData(t_drill, v_drill)
		self.velocity_time_curve_stop.setData(t_stop, v_stop)
		self.velocity_time_curve_retract.setData(t_retract, v_retract)
		if self.cb_autoscale.isChecked():
			self.depth_time_plot.enableAutoRange()
			self.velocity_time_plot.enableAutoRange()

	def _refresh_histogram(self):
		if not self.velocity_series_ms:
			if self._hist_bar is not None:
				try:
					self.hist_plot.removeItem(self._hist_bar)
				except Exception:
					pass
				self._hist_bar = None
			return
		arr = np.array(self.velocity_series_ms)
		if arr.size < 5:
			return
		
		# Chuyển đổi đơn vị vận tốc cho histogram
		converted_arr = self._convert_velocity_array(arr)
		
		# Tính range phù hợp với vận tốc khoan nhỏ
		v_min, v_max = np.min(converted_arr), np.max(converted_arr)
		if v_max - v_min < 0.001:  # Nếu range quá nhỏ, mở rộng một chút
			v_center = (v_min + v_max) / 2
			v_min = v_center - 0.005
			v_max = v_center + 0.005
		
		# Tạo bins với range phù hợp
		bins = np.linspace(v_min, v_max, 25)
		counts, edges = np.histogram(converted_arr, bins=bins)
		centers = (edges[:-1] + edges[1:]) / 2.0
		width = (edges[1] - edges[0]) * 0.8
		
		try:
			if self._hist_bar is not None:
				self.hist_plot.removeItem(self._hist_bar)
		except Exception:
			pass
		
		self._hist_bar = pg.BarGraphItem(x=centers, height=counts, width=width, brush=pg.mkBrush(120, 160, 240, 180))
		self.hist_plot.addItem(self._hist_bar)
		
		# Cập nhật label trục x
		self.hist_plot.setLabel('bottom', 'Vận tốc', units=self.velocity_unit)

	def _refresh_stats(self):
		try:
			current_depth = self.depth_series_m[-1] if self.depth_series_m else 0.0
			max_depth = max(self.depth_series_m) if self.depth_series_m else 0.0
			current_velocity = self.velocity_series_ms[-1] if self.velocity_series_ms else 0.0
			avg_velocity = sum(self.velocity_series_ms) / len(self.velocity_series_ms) if self.velocity_series_ms else 0.0
			min_velocity = min(self.velocity_series_ms) if self.velocity_series_ms else 0.0
			max_velocity = max(self.velocity_series_ms) if self.velocity_series_ms else 0.0
			total_samples = len(self.velocity_series_ms)
			state = self.state_series[-1] if self.state_series else ""

				# Chuyển đổi đơn vị cho hiển thị
			values = {
				"current_depth": f"{self._convert_depth_value(current_depth):.3f}",
				"max_depth": f"{self._convert_depth_value(max_depth):.3f}",
				"current_velocity": f"{self._convert_velocity_value(current_velocity):.3f}",
				"avg_velocity": f"{self._convert_velocity_value(avg_velocity):.3f}",
				"min_velocity": f"{self._convert_velocity_value(min_velocity):.3f}",
				"max_velocity": f"{self._convert_velocity_value(max_velocity):.3f}",
				"state": state,
				"velocity_threshold": f"{self._convert_velocity_value(self._velocity_threshold):.3f}",
				"total_samples": str(total_samples)
			}
			for i, (key, _) in enumerate(self.stats_rows.items()):
				item = self.stats_table.item(i, 1)
				if item:
					text_val = values.get(key, "--")
					item.setText(text_val)
					# Tô màu theo trạng thái
					if key == "state":
						stl = (text_val or "").lower()
						if stl.startswith('khoan'):
							item.setBackground(QColor(200, 255, 200))
						elif ('rút' in stl) or ('rut' in stl):
							item.setBackground(QColor(255, 230, 180))
						elif stl:
							item.setBackground(QColor(255, 200, 200))
						else:
							item.setBackground(QColor(240, 240, 240))
			# Tự động giãn hàng theo nội dung và cập nhật chiều cao bảng để hiển thị đầy đủ
			self.stats_table.resizeRowsToContents()
			header = self.stats_table.horizontalHeader()
			total_h = header.height()
			for i in range(self.stats_table.rowCount()):
				total_h += self.stats_table.rowHeight(i)
			self.stats_table.setFixedHeight(total_h + 6)
		except Exception as e:
			print(f"GeotechPanel stats error: {e}")

	def _clear_chart(self):
		self.line_drill.setData([], [])
		self.line_stop.setData([], [])
		self.line_retract.setData([], [])
		self.scatter_drill.setData([], [])
		self.scatter_stop.setData([], [])
		self.scatter_retract.setData([], [])
		self.plot_widget.enableAutoRange()
		# Cập nhật popout windows
		self._update_popout_windows()

	def _toggle_recording(self, state: int):
		self.is_recording = state == Qt.CheckState.Checked.value

	def _start_new_session(self):
		name = self.edt_name.text().strip()
		if not name:
			QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập tên hố khoan trước khi bắt đầu.")
			return
		self.current_borehole = {
			"name": name,
			"location": self.edt_location.text().strip(),
			"operator": self.edt_operator.text().strip(),
			"notes": self.txt_notes.toPlainText().strip(),
			"started_at": time.time()
		}
		self.depth_series_m.clear()
		self.velocity_series_ms.clear()
		self.quality_series.clear()
		self.time_series.clear()
		self.state_series.clear()
		self._refresh_plot()
		self._refresh_time_plots()
		self._refresh_histogram()
		self._refresh_stats()
		# Cập nhật popout windows
		self._update_popout_windows()
		self.cb_record.setChecked(True)

	def _ensure_borehole_dir(self) -> str:
		base_dir = os.path.join(os.getcwd(), 'boreholes')
		try:
			os.makedirs(base_dir, exist_ok=True)
		except Exception:
			pass
		return base_dir

	def _convert_depth_value(self, depth_m: float) -> float:
		"""Chuyển đổi độ sâu từ m sang đơn vị hiện tại"""
		if self.depth_unit == "mm":
			return depth_m * 1000
		elif self.depth_unit == "cm":
			return depth_m * 100
		return depth_m  # m

	def _convert_velocity_value(self, velocity_ms: float) -> float:
		"""Chuyển đổi vận tốc từ m/s sang đơn vị hiện tại"""
		if self.velocity_unit == "mm/s":
			return velocity_ms * 1000
		elif self.velocity_unit == "cm/s":
			return velocity_ms * 100
		return velocity_ms  # m/s

	def _convert_depth_array(self, depths_m):
		"""Chuyển đổi array độ sâu"""
		return [self._convert_depth_value(d) for d in depths_m]

	def _convert_velocity_array(self, velocities_ms):
		"""Chuyển đổi array vận tốc"""
		return [self._convert_velocity_value(v) for v in velocities_ms]

	def _on_depth_unit_changed(self, new_unit: str):
		"""Xử lý khi thay đổi đơn vị độ sâu"""
		self.depth_unit = new_unit
		self._update_plot_labels()
		self._update_stats_labels()
		self._refresh_plot()
		self._refresh_time_plots()
		self._refresh_stats()
		self._update_popout_windows()

	def _on_velocity_unit_changed(self, new_unit: str):
		"""Xử lý khi thay đổi đơn vị vận tốc"""
		self.velocity_unit = new_unit
		self._update_plot_labels()
		self._update_stats_labels()
		self._refresh_plot()
		self._refresh_time_plots()
		self._refresh_histogram()
		self._refresh_stats()
		self._update_popout_windows()

	def _update_plot_labels(self):
		"""Cập nhật labels của các plot theo đơn vị mới"""
		try:
			self.plot_widget.setLabel('left', 'Độ sâu', units=self.depth_unit)
			self.plot_widget.setLabel('bottom', 'Vận tốc', units=self.velocity_unit)
			
			self.depth_time_plot.setLabel('left', 'Độ sâu', units=self.depth_unit)
			self.velocity_time_plot.setLabel('left', 'Vận tốc', units=self.velocity_unit)
			self.hist_plot.setLabel('bottom', 'Vận tốc', units=self.velocity_unit)
		except Exception:
			pass

	def _update_stats_labels(self):
		"""Cập nhật labels của bảng thống kê theo đơn vị mới"""
		# Cập nhật headers trong stats_table
		new_labels = {
			"current_depth": f"Độ sâu hiện tại ({self.depth_unit})",
			"max_depth": f"Độ sâu tối đa ({self.depth_unit})",
			"current_velocity": f"Vận tốc hiện tại ({self.velocity_unit})",
			"avg_velocity": f"Vận tốc trung bình ({self.velocity_unit})",
			"min_velocity": f"Vận tốc nhỏ nhất ({self.velocity_unit})",
			"max_velocity": f"Vận tốc lớn nhất ({self.velocity_unit})",
			"state": "Trạng thái",
			"time_drilling_s": "Tổng thời gian khoan (s)",
			"time_stopped_s": "Tổng thời gian dừng (s)",
			"efficiency_percent": "Hiệu suất (%)",
			"velocity_threshold": f"Ngưỡng vận tốc ({self.velocity_unit})",
			"total_samples": "Số mẫu"
		}
		
		for i, (key, old_label) in enumerate(self.stats_rows.items()):
			if key in new_labels:
				self.stats_rows[key] = new_labels[key]
				item = self.stats_table.item(i, 0)
				if item:
					item.setText(new_labels[key])

	def _popout_plot(self, source_widget: pg.PlotWidget, title: str):
		"""Mở một cửa sổ riêng với đồ thị cập nhật realtime."""
		try:
			from PyQt6.QtWidgets import QDialog, QVBoxLayout
			
			# Custom dialog class để xử lý close event
			class PopoutWindow(QDialog):
				def __init__(self, parent, geotech_panel):
					super().__init__(parent)
					self.geotech_panel = geotech_panel
				
				def closeEvent(self, event):
					# Xóa khỏi danh sách popout windows
					self.geotech_panel.popout_windows = [w for w in self.geotech_panel.popout_windows if w['window'] != self]
					event.accept()
			
			win = PopoutWindow(self, self)
			win.setWindowTitle(f"{title} - Geotech (Realtime)")
			layout = QVBoxLayout(win)
			
			# Tạo plot mới
			new_plot = pg.PlotWidget()
			new_plot.setBackground('w')
			new_plot.showGrid(x=True, y=True)
			
			# Copy labels/titles với đơn vị hiện tại
			try:
				if title == "Velocity-Depth":
					new_plot.setLabel('left', 'Độ sâu', units=self.depth_unit)
					new_plot.setLabel('bottom', 'Vận tốc', units=self.velocity_unit)
					new_plot.getViewBox().invertY(True)
				elif title == "Depth-Time":
					new_plot.setLabel('left', 'Độ sâu', units=self.depth_unit)
					new_plot.setLabel('bottom', 'Thời gian', units='s')
					new_plot.getViewBox().invertY(True)
				elif title == "Velocity-Time":
					new_plot.setLabel('left', 'Vận tốc', units=self.velocity_unit)
					new_plot.setLabel('bottom', 'Thời gian', units='s')
				elif title == "Velocity-Histogram":
					new_plot.setLabel('left', 'Tần suất')
					new_plot.setLabel('bottom', 'Vận tốc', units=self.velocity_unit)
				new_plot.setTitle(f"{title} ({self.depth_unit}, {self.velocity_unit})")
			except Exception:
				pass
			
			# Tạo cấu trúc tương ứng với từng loại plot
			plot_info = {'window': win, 'plot': new_plot, 'title': title, 'items': {}}
			
			if title == "Velocity-Depth":
				# Tạo line và scatter items tương ứng
				plot_info['items']['line_drill'] = new_plot.plot([], [], pen=pg.mkPen(color=(0, 150, 0), width=2))
				plot_info['items']['line_stop'] = new_plot.plot([], [], pen=pg.mkPen(color=(200, 0, 0), width=2))
				plot_info['items']['line_retract'] = new_plot.plot([], [], pen=pg.mkPen(color=(240, 160, 0), width=2))
				plot_info['items']['scatter_drill'] = pg.ScatterPlotItem(size=6, pen=pg.mkPen(None), brush=pg.mkBrush(50, 180, 50, 200))
				plot_info['items']['scatter_stop'] = pg.ScatterPlotItem(size=6, pen=pg.mkPen(None), brush=pg.mkBrush(220, 60, 60, 200))
				plot_info['items']['scatter_retract'] = pg.ScatterPlotItem(size=6, pen=pg.mkPen(None), brush=pg.mkBrush(240, 160, 0, 200))
				new_plot.addItem(plot_info['items']['scatter_drill'])
				new_plot.addItem(plot_info['items']['scatter_stop'])
				new_plot.addItem(plot_info['items']['scatter_retract'])
				
			elif title == "Depth-Time":
				plot_info['items']['curve_drill'] = new_plot.plot([], [], pen=pg.mkPen(color=(0, 150, 0), width=2))
				plot_info['items']['curve_stop'] = new_plot.plot([], [], pen=pg.mkPen(color=(200, 0, 0), width=2))
				plot_info['items']['curve_retract'] = new_plot.plot([], [], pen=pg.mkPen(color=(240, 160, 0), width=2))
				
			elif title == "Velocity-Time":
				plot_info['items']['curve_drill'] = new_plot.plot([], [], pen=pg.mkPen(color=(0, 150, 0), width=2))
				plot_info['items']['curve_stop'] = new_plot.plot([], [], pen=pg.mkPen(color=(200, 0, 0), width=2))
				plot_info['items']['curve_retract'] = new_plot.plot([], [], pen=pg.mkPen(color=(240, 160, 0), width=2))
				# Thêm threshold lines với đơn vị chuyển đổi
				converted_thr = self._convert_velocity_value(self._velocity_threshold)
				vel_thr_pos = pg.InfiniteLine(angle=0, pos=converted_thr, pen=pg.mkPen(color=(0, 160, 0), style=Qt.PenStyle.DashLine))
				vel_thr_neg = pg.InfiniteLine(angle=0, pos=-converted_thr, pen=pg.mkPen(color=(200, 0, 0), style=Qt.PenStyle.DashLine))
				new_plot.addItem(vel_thr_pos)
				new_plot.addItem(vel_thr_neg)
				plot_info['items']['thr_pos'] = vel_thr_pos
				plot_info['items']['thr_neg'] = vel_thr_neg
				
			elif title == "Velocity-Histogram":
				plot_info['items']['hist_bar'] = None  # Sẽ được tạo khi có dữ liệu
			

			
			layout.addWidget(new_plot)
			self.popout_windows.append(plot_info)
			win.resize(900, 600)
			win.show()
			
			# Cập nhật ngay lập tức với dữ liệu hiện tại
			self._update_popout_windows()
			
		except Exception as e:
			print(f"Popout error: {e}")

	def _update_popout_windows(self):
		"""Cập nhật tất cả cửa sổ popout với dữ liệu mới nhất."""
		if not self.popout_windows:
			return
			
		for window_info in self.popout_windows[:]:  # Copy list để tránh lỗi khi modify
			try:
				title = window_info['title']
				items = window_info['items']
				
				if title == "Velocity-Depth":
					# Tách dữ liệu theo trạng thái với đơn vị chuyển đổi
					vel_drill, dep_drill = [], []
					vel_stop, dep_stop = [], []
					vel_retract, dep_retract = [], []
					for i in range(len(self.depth_series_m)):
						st = self.state_series[i] if i < len(self.state_series) else ""
						stl = st.lower()
						converted_vel = self._convert_velocity_value(self.velocity_series_ms[i])
						converted_dep = self._convert_depth_value(self.depth_series_m[i])
						if stl.startswith('khoan'):
							vel_drill.append(converted_vel)
							dep_drill.append(converted_dep)
						elif 'rút' in stl or 'rut' in stl:
							vel_retract.append(converted_vel)
							dep_retract.append(converted_dep)
						else:
							vel_stop.append(converted_vel)
							dep_stop.append(converted_dep)
					
					items['line_drill'].setData(vel_drill, dep_drill)
					items['line_stop'].setData(vel_stop, dep_stop)
					items['line_retract'].setData(vel_retract, dep_retract)
					items['scatter_drill'].setData(vel_drill, dep_drill)
					items['scatter_stop'].setData(vel_stop, dep_stop)
					items['scatter_retract'].setData(vel_retract, dep_retract)
					
				elif title == "Depth-Time":
					if self.time_series and self.depth_series_m:
						t0 = self.time_series[0]
						times = [t - t0 for t in self.time_series]
						t_drill, d_drill = [], []
						t_stop, d_stop = [], []
						t_retract, d_retract = [], []
						for i in range(len(times)):
							st = self.state_series[i] if i < len(self.state_series) else ""
							stl = st.lower()
							converted_dep = self._convert_depth_value(self.depth_series_m[i])
							if stl.startswith('khoan'):
								t_drill.append(times[i])
								d_drill.append(converted_dep)
							elif 'rút' in stl or 'rut' in stl:
								t_retract.append(times[i])
								d_retract.append(converted_dep)
							else:
								t_stop.append(times[i])
								d_stop.append(converted_dep)
						
						items['curve_drill'].setData(t_drill, d_drill)
						items['curve_stop'].setData(t_stop, d_stop)
						items['curve_retract'].setData(t_retract, d_retract)
					
				elif title == "Velocity-Time":
					if self.time_series and self.velocity_series_ms:
						t0 = self.time_series[0]
						times = [t - t0 for t in self.time_series]
						t_drill, v_drill = [], []
						t_stop, v_stop = [], []
						t_retract, v_retract = [], []
						for i in range(len(times)):
							st = self.state_series[i] if i < len(self.state_series) else ""
							stl = st.lower()
							converted_vel = self._convert_velocity_value(self.velocity_series_ms[i])
							if stl.startswith('khoan'):
								t_drill.append(times[i])
								v_drill.append(converted_vel)
							elif 'rút' in stl or 'rut' in stl:
								t_retract.append(times[i])
								v_retract.append(converted_vel)
							else:
								t_stop.append(times[i])
								v_stop.append(converted_vel)
						
						items['curve_drill'].setData(t_drill, v_drill)
						items['curve_stop'].setData(t_stop, v_stop)
						items['curve_retract'].setData(t_retract, v_retract)
						
						# Cập nhật threshold lines với đơn vị chuyển đổi
						if 'thr_pos' in items and 'thr_neg' in items:
							converted_thr = self._convert_velocity_value(self._velocity_threshold)
							items['thr_pos'].setValue(converted_thr)
							items['thr_neg'].setValue(-converted_thr)
					
				elif title == "Velocity-Histogram":
					if self.velocity_series_ms and len(self.velocity_series_ms) >= 5:
						import numpy as np
						arr = np.array(self.velocity_series_ms)
						counts, edges = np.histogram(arr, bins=20)
						centers = (edges[:-1] + edges[1:]) / 2.0
						width = (edges[1] - edges[0]) * 0.9
						
						# Xóa histogram cũ nếu có
						if items['hist_bar'] is not None:
							try:
								window_info['plot'].removeItem(items['hist_bar'])
							except Exception:
								pass
						
						# Tạo histogram mới
						items['hist_bar'] = pg.BarGraphItem(x=centers, height=counts, width=width, brush=pg.mkBrush(120, 160, 240, 180))
						window_info['plot'].addItem(items['hist_bar'])
						
			except Exception as e:
				print(f"Popout update error: {e}")
				# Xóa window lỗi khỏi danh sách
				self.popout_windows.remove(window_info)

	def _save_csv(self):
		if not self.depth_series_m or not self.velocity_series_ms:
			QMessageBox.information(self, "Không có dữ liệu", "Chưa có dữ liệu để lưu.")
			return
		name = self.current_borehole.get("name") or self.edt_name.text().strip()
		if not name:
			QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập tên hố khoan trước khi lưu.")
			return
		bdir = self._ensure_borehole_dir()
		ts_str = time.strftime('%Y%m%d_%H%M%S')
		default_path = os.path.join(bdir, f"{name}_{ts_str}.csv")
		filename, _ = QFileDialog.getSaveFileName(self, "Lưu dữ liệu hố khoan", default_path, "CSV Files (*.csv)")
		if not filename:
			return
		try:
			import csv
			with open(filename, 'w', newline='') as f:
				writer = csv.writer(f)
				writer.writerow([
					"timestamp", "depth_m", "velocity_ms", "state", "signal_quality",
					"borehole_name", "location", "operator", "notes"
				])
				meta = (
					self.current_borehole.get('name', ''),
					self.current_borehole.get('location', ''),
					self.current_borehole.get('operator', ''),
					self.current_borehole.get('notes', '')
				)
				for i in range(len(self.depth_series_m)):
					writer.writerow([
						self.time_series[i] if i < len(self.time_series) else '',
						f"{self.depth_series_m[i]:.6f}",
						f"{self.velocity_series_ms[i]:.6f}",
						self.state_series[i] if i < len(self.state_series) else '',
						self.quality_series[i] if i < len(self.quality_series) else '',
						meta[0], meta[1], meta[2], meta[3]
					])
			QMessageBox.information(self, "Đã lưu", f"Lưu dữ liệu thành công:\n{filename}")
		except Exception as e:
			QMessageBox.critical(self, "Lỗi", f"Không thể lưu CSV: {e}")

	@pyqtSlot(dict)
	def on_statistics_updated(self, stats: Dict[str, Any]):
		"""Nhận thống kê cập nhật từ DataProcessor để hiển thị trạng thái & thời gian & hiệu suất."""
		try:
			if 'velocity_threshold' in stats:
				try:
					self._velocity_threshold = float(stats['velocity_threshold'])
					self.vel_thr_pos.setValue(self._velocity_threshold)
					self.vel_thr_neg.setValue(-self._velocity_threshold)
					# Cập nhật threshold trong popout windows
					self._update_popout_windows()
				except Exception:
					pass
			# Cập nhật các giá trị nếu có
			mapping = {
				"time_drilling_s": lambda v: f"{float(v):.1f}",
				"time_stopped_s": lambda v: f"{float(v):.1f}",
				"efficiency_percent": lambda v: f"{float(v):.1f}",
				"state": lambda v: str(v),
			}
			for i, (key, _) in enumerate(self.stats_rows.items()):
				if key in mapping and key in stats:
					item = self.stats_table.item(i, 1)
					if item:
						text_val = mapping[key](stats[key])
						item.setText(text_val)
						# Tô màu theo trạng thái ngay khi cập nhật
						if key == 'state':
							stl = (text_val or "").lower()
							if stl.startswith('khoan'):
								item.setBackground(QColor(200, 255, 200))
							elif ('rút' in stl) or ('rut' in stl):
								item.setBackground(QColor(255, 230, 180))
							elif stl:
								item.setBackground(QColor(255, 200, 200))
							else:
								item.setBackground(QColor(240, 240, 240))
		except Exception:
			pass

