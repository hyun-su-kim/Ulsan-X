from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QLabel, QPushButton, QFrame,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from ulsan_gui.views.login_view    import LoginView
from ulsan_gui.views.map_view      import MapView
from ulsan_gui.views.robot_view    import RobotView
from ulsan_gui.views.log_view      import LogView
from ulsan_gui.views.settings_view import SettingsView

VIEWS = [
    ('map',      '🗺',  '지도'),
    ('robot',    '🤖',  '로봇'),
    ('log',      '📋',  '로그'),
    ('settings', '⚙',  '설정'),
]

VIEW_LABELS = {
    'map':      '지도',
    'robot':    '로봇',
    'log':      '로그',
    'settings': '설정',
}

PIN = '1234'

BUSY_STATES = {'BUSY', 'RETURNING', 'WAITING'}


class MainWindow(QMainWindow):
    def __init__(self, ros_node):
        super().__init__()
        self.ros = ros_node
        self._robot_statuses = {'limo1': 'UNKNOWN', 'limo2': 'UNKNOWN'}

        self.setWindowTitle('wego 관제 대시보드')
        self.resize(1280, 800)

        self._root = QStackedWidget()
        self.setCentralWidget(self._root)

        self._login_view = LoginView(PIN, self._on_login_success)
        self._root.addWidget(self._login_view)

        self._main_widget = self._build_main()
        self._root.addWidget(self._main_widget)
        self._root.setCurrentWidget(self._login_view)

        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

        self.ros.signals.sig_status_1.connect(lambda s: self._on_status('limo1', s))
        self.ros.signals.sig_status_2.connect(lambda s: self._on_status('limo2', s))

    # ── 메인 앱 레이아웃 ─────────────────────────────────────────────

    def _build_main(self) -> QWidget:
        root = QWidget()
        root.setStyleSheet('background:#f0f2f5;')
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        vbox.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_content(), 1)

        body_widget = QWidget()
        body_widget.setLayout(body)
        vbox.addWidget(body_widget, 1)

        return root

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet('background:#fff; border-bottom:1px solid #e0e4ea;')

        hbox = QHBoxLayout(header)
        hbox.setContentsMargins(16, 0, 16, 0)
        hbox.setSpacing(0)

        # 로고 아이콘 박스
        logo_icon = QLabel('W')
        logo_icon.setFixedSize(28, 28)
        logo_icon.setAlignment(Qt.AlignCenter)
        logo_icon.setFont(QFont('Segoe UI', 13, QFont.Bold))
        logo_icon.setStyleSheet('background:#1e40af; color:white; border-radius:6px;')
        hbox.addWidget(logo_icon)
        hbox.addSpacing(8)

        logo_text = QLabel('wego_ui')
        logo_text.setFont(QFont('Segoe UI', 16, QFont.Bold))
        logo_text.setStyleSheet('color:#1e40af;')
        hbox.addWidget(logo_text)
        hbox.addSpacing(20)

        # 브레드크럼
        self._breadcrumb = QLabel()
        self._breadcrumb.setFont(QFont('Segoe UI', 12))
        self._breadcrumb.setStyleSheet('color:#6b7280;')
        self._set_breadcrumb('지도 뷰')
        hbox.addWidget(self._breadcrumb)

        hbox.addStretch(1)

        # 통계 칩
        self._chip_total = _make_stat_chip('#6b7280', '전체',   '2')
        self._chip_busy  = _make_stat_chip('#f59e0b', '운행 중', '0')
        self._chip_idle  = _make_stat_chip('#10b981', '대기',   '0')
        for chip in (self._chip_total, self._chip_busy, self._chip_idle):
            hbox.addWidget(chip)
            hbox.addSpacing(6)

        # 구분선
        vline = QFrame()
        vline.setFrameShape(QFrame.VLine)
        vline.setFixedHeight(24)
        vline.setStyleSheet('color:#e5e7eb; border:none; border-left:1px solid #e5e7eb;')
        hbox.addSpacing(6)
        hbox.addWidget(vline)
        hbox.addSpacing(12)

        # 시계
        self._clock_label = QLabel('00:00:00')
        self._clock_label.setFont(QFont('Consolas', 11, QFont.Bold))
        self._clock_label.setStyleSheet('color:#374151;')
        hbox.addWidget(self._clock_label)
        hbox.addSpacing(12)

        # 사용자명
        user_lbl = QLabel('관리자')
        user_lbl.setFont(QFont('Segoe UI', 12))
        user_lbl.setStyleSheet('color:#6b7280;')
        hbox.addWidget(user_lbl)
        hbox.addSpacing(12)

        # 로그아웃
        logout_btn = QPushButton('로그아웃')
        logout_btn.setFixedHeight(28)
        logout_btn.setStyleSheet(
            'background:#f1f5f9; border:1px solid #e2e8f0; border-radius:6px;'
            'padding:0 10px; font-size:12px; color:#64748b;'
        )
        logout_btn.clicked.connect(self._logout)
        hbox.addWidget(logout_btn)

        return header

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setFixedWidth(56)
        sidebar.setStyleSheet('background:#1e293b; border-right:1px solid #334155;')

        vbox = QVBoxLayout(sidebar)
        vbox.setContentsMargins(0, 12, 0, 12)
        vbox.setSpacing(4)
        vbox.setAlignment(Qt.AlignTop)

        self._sb_btns: dict[str, QPushButton] = {}
        for i, (key, icon, label) in enumerate(VIEWS):
            # 로봇 ↔ 로그 사이 구분선
            if i == 2:
                sep = QFrame()
                sep.setFixedSize(30, 1)
                sep.setStyleSheet('background:#334155; border:none;')
                vbox.addWidget(sep, alignment=Qt.AlignHCenter)
                vbox.addSpacing(4)

            # 아이콘 + 레이블 묶음
            cell = QWidget()
            cell_vbox = QVBoxLayout(cell)
            cell_vbox.setContentsMargins(0, 0, 0, 0)
            cell_vbox.setSpacing(1)
            cell_vbox.setAlignment(Qt.AlignCenter)

            btn = QPushButton(icon)
            btn.setFixedSize(38, 38)
            btn.setFont(QFont('Segoe UI', 17))
            btn.setStyleSheet(self._sb_style(False))
            btn.clicked.connect(lambda _, k=key: self._switch_view(k))
            self._sb_btns[key] = btn
            cell_vbox.addWidget(btn, alignment=Qt.AlignCenter)

            lbl = QLabel(label)
            lbl.setFont(QFont('Segoe UI', 7))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet('color:#94a3b8; background:transparent;')
            cell_vbox.addWidget(lbl)

            vbox.addWidget(cell, alignment=Qt.AlignHCenter)

        return sidebar

    def _build_content(self) -> QStackedWidget:
        self._stack = QStackedWidget()
        self._views: dict[str, QWidget] = {}

        for key, _, _ in VIEWS:
            view = self._make_view(key)
            self._views[key] = view
            self._stack.addWidget(view)

        self._switch_view('map')
        return self._stack

    def _make_view(self, key: str) -> QWidget:
        if key == 'map':      return MapView(self.ros)
        if key == 'robot':    return RobotView(self.ros)
        if key == 'log':      return LogView(self.ros)
        if key == 'settings': return SettingsView(self.ros)
        return QLabel(key)

    # ── 뷰 전환 ──────────────────────────────────────────────────────

    def _switch_view(self, key: str) -> None:
        self._stack.setCurrentWidget(self._views[key])
        for k, btn in self._sb_btns.items():
            btn.setStyleSheet(self._sb_style(k == key))
        self._set_breadcrumb(VIEW_LABELS[key])

    @staticmethod
    def _sb_style(active: bool) -> str:
        if active:
            return 'background:#1e40af; color:#fff; border:none; border-radius:8px;'
        return 'background:transparent; color:#94a3b8; border:none; border-radius:8px;'

    def _set_breadcrumb(self, view_label: str) -> None:
        self._breadcrumb.setText(
            f'🏠  <span style="color:#9ca3af;">›</span>  '
            f'<span style="color:#374151;font-weight:600;">{view_label}</span>'
        )

    # ── 로그인 / 로그아웃 ────────────────────────────────────────────

    def _on_login_success(self) -> None:
        self._root.setCurrentWidget(self._main_widget)

    def _logout(self) -> None:
        self._login_view.reset()
        self._root.setCurrentWidget(self._login_view)

    # ── 상태 / 시계 업데이트 ─────────────────────────────────────────

    def _on_status(self, robot: str, status: str) -> None:
        self._robot_statuses[robot] = status
        statuses = list(self._robot_statuses.values())
        busy = sum(1 for s in statuses if s in BUSY_STATES)
        idle = sum(1 for s in statuses if s == 'IDLE')
        self._chip_busy._val.setText(str(busy))
        self._chip_idle._val.setText(str(idle))

    def _tick_clock(self) -> None:
        self._clock_label.setText(datetime.now().strftime('%H:%M:%S'))


# ── 통계 칩 헬퍼 ─────────────────────────────────────────────────────

def _make_stat_chip(dot_color: str, label: str, count: str) -> QWidget:
    chip = QWidget()
    chip.setFixedHeight(26)
    chip.setStyleSheet('background:#f3f4f6; border-radius:13px;')
    row = QHBoxLayout(chip)
    row.setContentsMargins(10, 0, 10, 0)
    row.setSpacing(5)

    dot = QLabel()
    dot.setFixedSize(8, 8)
    dot.setStyleSheet(f'background:{dot_color}; border-radius:4px; border:none;')
    row.addWidget(dot)

    lbl = QLabel(label)
    lbl.setFont(QFont('Segoe UI', 11))
    lbl.setStyleSheet('color:#374151; background:transparent;')
    row.addWidget(lbl)

    val = QLabel(count)
    val.setFont(QFont('Segoe UI', 13, QFont.Bold))
    val.setStyleSheet('color:#111827; background:transparent;')
    row.addWidget(val)

    chip._val = val
    return chip
