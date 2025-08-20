"""
Charts Panel - Tab hiển thị đồ thị real-time và bảng thông số
"""
import time
import numpy as np # type: ignore[attr-defined]
from typing import Dict, Any
from PyQt6.QtWidgets import ( # type: ignore[attr-defined]
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGroupBox,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel, QCheckBox,
    QHeaderView
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot # type: ignore[attr-defined]
from PyQt6.QtGui import QFont # type: ignore[attr-defined]
import pyqtgraph as pg # type: ignore[attr-defined]

# Cấu hình chung cho pyqtgraph để hiển thị mượt và gọn
pg.setConfigOptions(antialias=True)

class RealTimeChart(QWidget):
    """Widget đồ thị real-time"""
    
    def __init__(self, title: str, y_label: str, y_unit: str = "", max_points: int = 100):
        super().__init__()
        self.title = title
        self.y_label = y_label
        self.y_unit = y_unit
        self.max_points = max_points
        
        # Data storage
        self.x_data = []
        self.y_data = []
        self.start_time = time.time()
        
        self.setup_ui()
        
    def setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        
        # Chart widget
        self.plot_widget = pg.PlotWidget()
        # Đặt nhãn trục Y nằm ngang để không bị đè
        self.plot_widget.setLabel('left', self.y_label, units=self.y_unit, angle=0)
        self.plot_widget.setLabel('bottom', 'Thời gian', units='s')
        self.plot_widget.setTitle(self.title, color='k', size='12pt')
        # Thêm margins để nhãn/giá trị không đè nhau
        try:
            self.plot_widget.getPlotItem().setContentsMargins(12, 6, 8, 8)
        except Exception:
            pass
        # Chiều cao tối thiểu để trục không bị chèn ép
        self.plot_widget.setMinimumHeight(260)
        # Tạo padding giữa tick labels và axis label bằng GridLayout spacing
        try:
            pi = self.plot_widget.getPlotItem()
            grid = pi.layout
            # Hàng 3: trục dưới; Hàng 4: nhãn dưới -> tăng khoảng cách giữa 3 và 4
            grid.setRowSpacing(4, 18)
            # Cột 0: nhãn trái; Cột 1: trục trái -> tăng khoảng cách giữa 0 và 1
            grid.setColumnSpacing(1, 18)
        except Exception:
            pass
        
        # Configure plot
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setBackground('w')  # White background
        # Cố định bề rộng/chiều cao trục và giảm cỡ chữ để tránh đè nhãn
        try:
            axis_left = self.plot_widget.getAxis('left')
            axis_bottom = self.plot_widget.getAxis('bottom')
            small_font = QFont("Arial", 9)
            axis_left.setStyle(tickFont=small_font, autoExpandTextSpace=True, tickTextOffset=12)
            axis_bottom.setStyle(tickFont=small_font, autoExpandTextSpace=True, tickTextOffset=12)
            # Font cho nhãn trục để rõ ràng
            label_font = QFont("Arial", 10, QFont.Weight.Medium)
            axis_left.label.setFont(label_font)
            axis_bottom.label.setFont(label_font)
            # Bề rộng/chiều cao trục đủ rộng cho số nhiều chữ số
            # Tăng width trục trái để nhãn nằm ngang có chỗ
            axis_left.setWidth(120)
            axis_bottom.setHeight(52)
            # Thêm padding không gian trống quanh vùng vẽ để nhãn không đè
            vb = self.plot_widget.getViewBox()
            vb.setDefaultPadding(0.03)
        except Exception:
            pass
        
        # Plot curve
        pen = pg.mkPen(color='b', width=2)
        self.curve = self.plot_widget.plot([], [], pen=pen)
        
        layout.addWidget(self.plot_widget)
        
        # Controls
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        self.auto_scale_cb = QCheckBox("Auto Scale Y")
        self.auto_scale_cb.setChecked(True)
        self.auto_scale_cb.stateChanged.connect(self._on_auto_scale_changed)
        
        self.clear_btn = QPushButton("Xóa dữ liệu")
        self.clear_btn.clicked.connect(self.clear_data)
        
        self.current_value_label = QLabel("--")
        self.current_value_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        
        controls_layout.addWidget(QLabel("Giá trị hiện tại:"))
        controls_layout.addWidget(self.current_value_label)
        controls_layout.addStretch()
        controls_layout.addWidget(self.auto_scale_cb)
        controls_layout.addWidget(self.clear_btn)
        
        layout.addLayout(controls_layout)
        
    def add_data_point(self, value: float):
        """Thêm điểm dữ liệu mới"""
        current_time = time.time() - self.start_time
        
        self.x_data.append(current_time)
        self.y_data.append(value)
        
        # Giới hạn số điểm
        if len(self.x_data) > self.max_points:
            self.x_data = self.x_data[-self.max_points:]
            self.y_data = self.y_data[-self.max_points:]
            
        # Update plot
        self.curve.setData(self.x_data, self.y_data)
        
        # Update current value label
        self.current_value_label.setText(f"{value:.2f} {self.y_unit}")
        
        # Auto scale if enabled
        if self.auto_scale_cb.isChecked():
            self.plot_widget.enableAutoRange()
            
    def clear_data(self):
        """Xóa tất cả dữ liệu"""
        self.x_data.clear()
        self.y_data.clear()
        self.curve.setData([], [])
        self.current_value_label.setText("--")
        self.start_time = time.time()
        
    def _on_auto_scale_changed(self, state):
        """Xử lý thay đổi auto scale"""
        if state == Qt.CheckState.Checked.value:
            self.plot_widget.enableAutoRange()
        else:
            self.plot_widget.disableAutoRange()

class StatsTable(QWidget):
    """Bảng hiển thị thông số real-time"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        
        # Group box
        group_box = QGroupBox("Thông Số Thiết Bị")
        group_layout = QVBoxLayout(group_box)
        
        # Table widget
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Thông số", "Giá trị"])
        
        # Configure table
        header = self.table.horizontalHeader()
        # Để cột giá trị luôn đủ rộng theo không gian còn lại
        header.setStretchLastSection(True)
        # Không elide text tiêu đề; cho phép người dùng kéo thay đổi độ rộng cột
        try:
            header.setTextElideMode(Qt.TextElideMode.ElideNone)
        except Exception:
            pass
        header.setMinimumSectionSize(120)
        # Cột "Thông số" cho phép kéo tự do, cột "Giá trị" tự giãn lấp đầy
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        # Đặt độ rộng ban đầu hợp lý cho cột tên; cột giá trị sẽ tự giãn
        try:
            header.resizeSection(0, 240)
        except Exception:
            pass
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setWordWrap(False)
        
        # Initialize rows
        self.stats_rows = {
            'current_distance': 'Khoảng cách hiện tại (mm)',
            'current_velocity': 'Vận tốc hiện tại (m/s)', 
            'current_quality': 'Chất lượng tín hiệu (%)',
            'measurement_rate': 'Tần số đo (Hz)',
            'avg_distance': 'Khoảng cách trung bình (mm)',
            'min_distance': 'Khoảng cách tối thiểu (mm)',
            'max_distance': 'Khoảng cách tối đa (mm)',
            'total_samples': 'Tổng số mẫu',
            'input_voltage': 'Điện áp đầu vào (V)',
            'hardware_version': 'Phiên bản phần cứng',
            'software_version': 'Phiên bản phần mềm',
            'serial_number': 'Số serial',
            'device_status': 'Trạng thái thiết bị'
        }
        
        self.table.setRowCount(len(self.stats_rows))
        
        # Populate table with labels
        for i, (key, label) in enumerate(self.stats_rows.items()):
            name_item = QTableWidgetItem(label)
            value_item = QTableWidgetItem("--")
            name_item.setToolTip(label)
            value_item.setToolTip("--")
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, value_item)
            
        group_layout.addWidget(self.table)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("Export CSV")
        self.export_btn.clicked.connect(self._export_data)
        
        self.reset_stats_btn = QPushButton("Reset Thống kê")
        self.reset_stats_btn.clicked.connect(self._reset_stats)
        
        controls_layout.addWidget(self.export_btn)
        controls_layout.addWidget(self.reset_stats_btn)
        controls_layout.addStretch()
        
        group_layout.addLayout(controls_layout)
        layout.addWidget(group_box)
        
    def update_stats(self, stats: Dict[str, Any]):
        """Cập nhật bảng thống kê"""
        for i, (key, label) in enumerate(self.stats_rows.items()):
            if key in stats:
                value = stats[key]
                
                # Format giá trị
                if isinstance(value, float):
                    if key in ['current_distance', 'avg_distance', 'min_distance', 'max_distance']:
                        formatted_value = f"{value:.1f}"
                    elif key in ['current_velocity', 'input_voltage']:
                        formatted_value = f"{value:.3f}"
                    elif key == 'measurement_rate':
                        formatted_value = f"{value:.1f}"
                    else:
                        formatted_value = f"{value:.2f}"
                elif isinstance(value, int):
                    formatted_value = str(value)
                else:
                    formatted_value = str(value)
                    
                # Update table item
                item = self.table.item(i, 1)
                if item:
                    item.setText(formatted_value)
                    item.setToolTip(formatted_value)
                    
                    # Color coding cho một số giá trị
                    if key == 'current_quality':
                        if isinstance(value, (int, float)):
                            from PyQt6.QtGui import QColor
                            if value >= 80:
                                item.setBackground(QColor(144, 238, 144))  # Light green
                            elif value >= 60:
                                item.setBackground(QColor(255, 255, 0))    # Yellow
                            else:
                                item.setBackground(QColor(211, 211, 211))  # Light gray
                                
    def _export_data(self):
        """Export dữ liệu"""
        # TODO: Implement export functionality
        # Có thể connect với DataProcessor để export
        pass
        
    def _reset_stats(self):
        """Reset thống kê"""
        # TODO: Emit signal để reset DataProcessor
        pass
        
    # (Đã loại bỏ các hàm simulate test data)

class ChartsPanel(QWidget):
    """Panel chính chứa đồ thị và bảng thông số"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
        # Timer để update charts
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(100)  # Update every 100ms
        
    def setup_ui(self):
        """Thiết lập giao diện"""
        layout = QVBoxLayout(self)
        
        # Main splitter (horizontal)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Charts
        charts_widget = QWidget()
        charts_layout = QVBoxLayout(charts_widget)
        charts_layout.setContentsMargins(16, 20, 16, 20)
        charts_layout.setSpacing(20)
        
        # Charts splitter (vertical)
        charts_splitter = QSplitter(Qt.Orientation.Vertical)
        charts_splitter.setHandleWidth(8)
        # Tăng khoảng cách giữa các widget trong splitter
        charts_splitter.setChildrenCollapsible(False)
        
        # Distance chart
        self.distance_chart = RealTimeChart(
            title="Khoảng Cách Theo Thời Gian",
            y_label="Khoảng cách",
            y_unit="mm",
            max_points=200
        )
        charts_splitter.addWidget(self.distance_chart)
        
        # Velocity chart
        self.velocity_chart = RealTimeChart(
            title="Vận Tốc Theo Thời Gian", 
            y_label="Vận tốc",
            y_unit="m/s",
            max_points=200
        )
        charts_splitter.addWidget(self.velocity_chart)
        
        # Đặt tỷ lệ cố định cho splitter để tạo khoảng cách đều
        charts_splitter.setSizes([1, 1])  # Chia đôi đều
        charts_splitter.setStretchFactor(0, 1)
        charts_splitter.setStretchFactor(1, 1)
        
        # Đồng bộ kích thước trục trái giữa 2 đồ thị để không bị lệch
        try:
            # Ẩn nhãn/giá trị trục X của đồ thị trên để tránh trùng lặp với đồ thị dưới
            self.distance_chart.plot_widget.getAxis('bottom').setStyle(showValues=False)
            self.distance_chart.plot_widget.setLabel('bottom', '')
            self.distance_chart.plot_widget.getAxis('bottom').setHeight(12)

            left_width = max(
                self.distance_chart.plot_widget.getAxis('left').width(),
                self.velocity_chart.plot_widget.getAxis('left').width()
            )
            self.distance_chart.plot_widget.getAxis('left').setWidth(left_width)
            self.velocity_chart.plot_widget.getAxis('left').setWidth(left_width)
            # Liên kết trục thời gian để nhãn X đồng bộ, dễ đọc hơn
            self.velocity_chart.plot_widget.setXLink(self.distance_chart.plot_widget)
        except Exception:
            pass
        
        charts_layout.addWidget(charts_splitter)
        main_splitter.addWidget(charts_widget)
        
        # Right side - Stats table
        self.stats_table = StatsTable()
        main_splitter.addWidget(self.stats_table)
        
        # Set splitter proportions - Cân đối 65/35 và giữ tỉ lệ khi kéo
        main_splitter.setSizes([650, 250])
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 2)
        
        layout.addWidget(main_splitter)
        
    @pyqtSlot(dict)
    def update_measurement_data(self, data: Dict[str, Any]):
        """Cập nhật dữ liệu đo mới"""
        # Update distance chart
        if 'distance_mm' in data:
            self.distance_chart.add_data_point(data['distance_mm'])
            
        # Update velocity chart
        if 'velocity_ms' in data:
            self.velocity_chart.add_data_point(data['velocity_ms'])
            
    @pyqtSlot(dict)
    def update_statistics(self, stats: Dict[str, Any]):
        """Cập nhật bảng thống kê"""
        self.stats_table.update_stats(stats)
        
    def _update_display(self):
        """Update display định kỳ"""
        # Có thể thêm logic update khác nếu cần
        pass
        
    def clear_all_data(self):
        """Xóa tất cả dữ liệu"""
        self.distance_chart.clear_data()
        self.velocity_chart.clear_data()