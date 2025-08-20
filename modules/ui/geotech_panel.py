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
	QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, QHeaderView, QAbstractItemView, QStyledItemDelegate
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
		try:
			# Quay ngược đồ thị: để độ sâu tăng dần theo trục Y hướng lên trên (chuẩn toán học)
			self.plot_widget.getViewBox().invertY(False)
			axis_left = self.plot_widget.getAxis('left')
			axis_bottom = self.plot_widget.getAxis('bottom')
			small_font = QFont('Arial', 9)
			axis_left.setStyle(tickFont=small_font, autoExpandTextSpace=True, tickTextOffset=12)
			axis_bottom.setStyle(tickFont=small_font, autoExpandTextSpace=True, tickTextOffset=12)
			axis_left.setWidth(120)
			axis_bottom.setHeight(48)
		except Exception:
			pass

		# Đường cong (line) và scatter để nhìn rõ các điểm
		self.curve = self.plot_widget.plot([], [], pen=pg.mkPen(color='b', width=2))
		self.scatter = pg.ScatterPlotItem(size=6, pen=pg.mkPen(None), brush=pg.mkBrush(50, 150, 255, 180))
		self.plot_widget.addItem(self.scatter)

		# Thanh công cụ đơn giản
		toolbar = QHBoxLayout()
		self.cb_autoscale = QCheckBox("Auto scale")
		self.cb_autoscale.setChecked(True)
		self.btn_clear_chart = QPushButton("Xóa biểu đồ")
		self.btn_clear_chart.clicked.connect(self._clear_chart)
		self.lbl_current = QLabel("Độ sâu: -- m | Vận tốc: -- m/s")
		self.lbl_current.setFont(QFont('Arial', 11, QFont.Weight.Bold))
		toolbar.addWidget(self.lbl_current)
		toolbar.addStretch()
		toolbar.addWidget(self.cb_autoscale)
		toolbar.addWidget(self.btn_clear_chart)

		chart_layout.addLayout(toolbar)
		chart_layout.addWidget(self.plot_widget)
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
			"total_samples": "Số mẫu (phiên hiện tại)"
		}
		self.stats_table.setRowCount(len(self.stats_rows))
		for i, (key, label) in enumerate(self.stats_rows.items()):
			name_item = QTableWidgetItem(label)
			value_item = QTableWidgetItem("--")
			# Căn chỉnh để cân đối hiển thị
			value_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
			self.stats_table.setItem(i, 0, name_item)
			self.stats_table.setItem(i, 1, value_item)

		# Cân đối bảng: cột tên có thể kéo, cột giá trị giãn hết còn lại
		header = self.stats_table.horizontalHeader()
		header.setStretchLastSection(True)
		header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
		header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
		try:
			header.resizeSection(0, 260)
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
		# Gắn delegate để vẽ đường phân cách giữa hai cột
		self.stats_table.setItemDelegate(ColumnSeparatorDelegate(self.stats_table))
		# Ấn định chiều cao theo số dòng để hộp cân đối, không xuất hiện thanh cuộn
		row_h = 28
		for i in range(len(self.stats_rows)):
			self.stats_table.setRowHeight(i, row_h)
		try:
			hh = header.height()
			self.stats_table.setFixedHeight(hh + row_h * len(self.stats_rows) + 6)
		except Exception:
			pass
		stats_layout.addWidget(self.stats_table)

		right_layout.addWidget(stats_group)
		right_layout.addStretch()

		main_splitter.addWidget(right_container)
		# Mở rộng khung đồ thị nhưng cho phép panel phải rộng hơn để bảng cân đối
		main_splitter.setSizes([1080, 420])
		main_splitter.setStretchFactor(0, 5)
		main_splitter.setStretchFactor(1, 1)

		layout.addWidget(main_splitter)

	@pyqtSlot(dict)
	def on_new_processed_data(self, data: Dict[str, Any]):
		"""Nhận dữ liệu từ DataProcessor và cập nhật biểu đồ + bảng."""
		try:
			depth_m: Optional[float] = None
			velocity_ms: Optional[float] = None
			quality: Optional[int] = None
			ts: float = data.get('timestamp', time.time())

			if 'distance_m' in data:
				depth_m = float(data['distance_m'])
			elif 'distance_mm' in data:
				depth_m = float(data['distance_mm']) / 1000.0

			if 'velocity_ms' in data:
				velocity_ms = float(data['velocity_ms'])
			if 'signal_quality' in data:
				quality = int(data['signal_quality'])

			if depth_m is None or velocity_ms is None:
				return

			# Cập nhật nhãn nhanh
			self.lbl_current.setText(f"Độ sâu: {depth_m:.3f} m | Vận tốc: {velocity_ms:.3f} m/s")

			if not self.is_recording:
				# Vẫn cập nhật đồ thị để xem realtime, nhưng không lưu series nếu không ghi
				self._update_plot_preview(depth_m, velocity_ms)
				return

			# Ghi dữ liệu vào series
			self.depth_series_m.append(depth_m)
			self.velocity_series_ms.append(velocity_ms)
			self.time_series.append(ts)
			self.quality_series.append(quality if quality is not None else 0)

			self._refresh_plot()
			self._refresh_stats()
		except Exception as e:
			print(f"GeotechPanel update error: {e}")

	def _update_plot_preview(self, depth_m: float, velocity_ms: float):
		"""Hiển thị nhanh điểm gần nhất khi không ghi dữ liệu."""
		self.curve.setData([velocity_ms], [depth_m])
		self.scatter.setData([velocity_ms], [depth_m])
		if self.cb_autoscale.isChecked():
			self.plot_widget.enableAutoRange()

	def _refresh_plot(self):
		if not self.depth_series_m or not self.velocity_series_ms:
			self.curve.setData([], [])
			self.scatter.setData([], [])
			return
		self.curve.setData(self.velocity_series_ms, self.depth_series_m)
		self.scatter.setData(self.velocity_series_ms, self.depth_series_m)
		if self.cb_autoscale.isChecked():
			self.plot_widget.enableAutoRange()

	def _refresh_stats(self):
		try:
			current_depth = self.depth_series_m[-1] if self.depth_series_m else 0.0
			max_depth = max(self.depth_series_m) if self.depth_series_m else 0.0
			current_velocity = self.velocity_series_ms[-1] if self.velocity_series_ms else 0.0
			avg_velocity = sum(self.velocity_series_ms) / len(self.velocity_series_ms) if self.velocity_series_ms else 0.0
			min_velocity = min(self.velocity_series_ms) if self.velocity_series_ms else 0.0
			max_velocity = max(self.velocity_series_ms) if self.velocity_series_ms else 0.0
			total_samples = len(self.velocity_series_ms)

			values = {
				"current_depth": f"{current_depth:.3f}",
				"max_depth": f"{max_depth:.3f}",
				"current_velocity": f"{current_velocity:.3f}",
				"avg_velocity": f"{avg_velocity:.3f}",
				"min_velocity": f"{min_velocity:.3f}",
				"max_velocity": f"{max_velocity:.3f}",
				"total_samples": str(total_samples)
			}
			for i, (key, _) in enumerate(self.stats_rows.items()):
				item = self.stats_table.item(i, 1)
				if item:
					item.setText(values.get(key, "--"))
		except Exception as e:
			print(f"GeotechPanel stats error: {e}")

	def _clear_chart(self):
		self.curve.setData([], [])
		self.scatter.setData([], [])
		self.plot_widget.enableAutoRange()

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
		self._refresh_plot()
		self._refresh_stats()
		self.cb_record.setChecked(True)

	def _ensure_borehole_dir(self) -> str:
		base_dir = os.path.join(os.getcwd(), 'boreholes')
		try:
			os.makedirs(base_dir, exist_ok=True)
		except Exception:
			pass
		return base_dir

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
					"timestamp", "depth_m", "velocity_ms", "signal_quality",
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
						self.quality_series[i] if i < len(self.quality_series) else '',
						meta[0], meta[1], meta[2], meta[3]
					])
			QMessageBox.information(self, "Đã lưu", f"Lưu dữ liệu thành công:\n{filename}")
		except Exception as e:
			QMessageBox.critical(self, "Lỗi", f"Không thể lưu CSV: {e}")

