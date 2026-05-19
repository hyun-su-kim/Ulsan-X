import csv
import io
from datetime import datetime

import requests
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QFileDialog,
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

API_URL = 'http://localhost:8000/logs'

_COMBO_STYLE = (
    'QComboBox { border:1px solid #d1d5db; border-radius:6px; padding:4px 10px;'
    '  background:#fff; color:#111827; min-width:90px; }'
    'QComboBox:hover { border-color:#9ca3af; }'
    'QComboBox::drop-down { border:none; width:20px; }'
    'QComboBox QAbstractItemView {'
    '  background:#fff; color:#111827; border:1px solid #d1d5db;'
    '  selection-background-color:#eff6ff; selection-color:#1e40af; outline:0; }'
)

LOG_TYPE_COLOR = {
    'mission_start':    ('#fffbeb', '#d97706'),
    'mission_complete': ('#f0fdf4', '#16a34a'),
    'mission_fail':     ('#fef2f2', '#dc2626'),
    'waiting':          ('#faf5ff', '#9333ea'),
    'system':           ('#f8fafc', '#374151'),
}

COLUMNS = ['시각', '로봇', '유형', '내용', '방문자']


class LogFetchThread(QThread):
    fetched = pyqtSignal(list)

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self) -> None:
        try:
            resp = requests.get(self._url, timeout=3)
            if resp.ok:
                self.fetched.emit(resp.json())
        except Exception:
            pass


class LogView(QWidget):
    def __init__(self, ros_node):
        super().__init__()
        self.ros = ros_node
        self._all_logs: list[dict] = []
        self._build_ui()

        self._timer = QTimer()
        self._timer.timeout.connect(self._fetch)
        self._timer.start(5000)
        self._fetch()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(10)

        # 툴바
        toolbar = QHBoxLayout()

        title = QLabel('📋 미션 로그')
        title.setFont(QFont('Segoe UI', 13, QFont.Bold))
        title.setStyleSheet('color:#111827;')
        toolbar.addWidget(title)
        toolbar.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText('🔍 검색...')
        self._search.setFixedWidth(200)
        self._search.setStyleSheet(
            'border:1px solid #d1d5db; border-radius:6px; padding:5px 10px;'
        )
        self._search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search)

        self._type_combo = QComboBox()
        self._type_combo.addItems(['전체', '임무시작', '임무완료', '임무실패', '대기', '시스템'])
        self._type_combo.setStyleSheet(_COMBO_STYLE)
        self._type_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self._type_combo)

        self._robot_combo = QComboBox()
        self._robot_combo.addItems(['전체', 'LIMO 1', 'LIMO 2'])
        self._robot_combo.setStyleSheet(_COMBO_STYLE)
        self._robot_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self._robot_combo)

        refresh_btn = QPushButton('🔄 새로고침')
        refresh_btn.setStyleSheet(
            'background:#f1f5f9; border:1px solid #d1d5db; border-radius:6px;'
            'padding:5px 12px; color:#374151;'
        )
        refresh_btn.clicked.connect(self._fetch)
        toolbar.addWidget(refresh_btn)

        csv_btn = QPushButton('⬇ CSV')
        csv_btn.setStyleSheet(
            'background:#1e40af; color:#fff; border:none; border-radius:6px; padding:5px 12px;'
        )
        csv_btn.clicked.connect(self._export_csv)
        toolbar.addWidget(csv_btn)

        vbox.addLayout(toolbar)

        # 테이블
        self._table = QTableWidget()
        self._table.setColumnCount(len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._table.horizontalHeader().setFont(QFont('Segoe UI', 10, QFont.Bold))
        self._table.setFont(QFont('Segoe UI', 10))
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(
            'QTableWidget { border:1px solid #e5e7eb; border-radius:8px;'
            '  background:#fff; gridline-color:#f3f4f6; }'
            'QHeaderView::section { background:#f8fafc; border:none;'
            '  border-bottom:1px solid #e5e7eb; padding:6px; }'
            'QTableWidget::item:selected { background:#eff6ff; color:#1e40af; }'
        )
        vbox.addWidget(self._table, 1)

        # 하단 카운트
        self._count_label = QLabel('총 0건')
        self._count_label.setFont(QFont('Segoe UI', 10))
        self._count_label.setStyleSheet('color:#6b7280;')
        vbox.addWidget(self._count_label, alignment=Qt.AlignRight)

    # ── 데이터 ────────────────────────────────────────────────────────

    def _fetch(self) -> None:
        self._thread = LogFetchThread(API_URL)
        self._thread.fetched.connect(self._on_fetched)
        self._thread.start()

    def _on_fetched(self, logs: list) -> None:
        self._all_logs = logs
        self._apply_filter()

    def _apply_filter(self) -> None:
        keyword = self._search.text().lower()
        type_idx  = self._type_combo.currentIndex()
        robot_idx = self._robot_combo.currentIndex()

        type_map = {1: 'mission_start', 2: 'mission_complete',
                    3: 'mission_fail',  4: 'waiting', 5: 'system'}

        filtered = []
        for log in self._all_logs:
            if type_idx > 0 and log.get('type') != type_map.get(type_idx):
                continue
            if robot_idx == 1 and log.get('robot') != 'limo1':
                continue
            if robot_idx == 2 and log.get('robot') != 'limo2':
                continue
            text = ' '.join(str(v) for v in log.values()).lower()
            if keyword and keyword not in text:
                continue
            filtered.append(log)

        self._render(filtered)

    def _render(self, logs: list) -> None:
        self._table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            log_type = log.get('type', 'system')
            bg, fg = LOG_TYPE_COLOR.get(log_type, ('#fff', '#374151'))

            cells = [
                log.get('timestamp', ''),
                log.get('robot', '').upper(),
                log.get('type', ''),
                log.get('message', ''),
                log.get('visitor', ''),
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                item.setForeground(QColor(fg))
                item.setBackground(QColor(bg))
                self._table.setItem(row, col, item)

        self._table.scrollToBottom()
        self._count_label.setText(f'총 {len(logs)}건')

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, 'CSV 저장', f'wego_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
            'CSV Files (*.csv)'
        )
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(COLUMNS)
            for row in range(self._table.rowCount()):
                writer.writerow([
                    self._table.item(row, col).text() if self._table.item(row, col) else ''
                    for col in range(len(COLUMNS))
                ])
