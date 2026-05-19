from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QLabel, QPushButton, QFrame,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from ulsan_gui.views.login_view   import LoginView
from ulsan_gui.views.map_view     import MapView
from ulsan_gui.views.robot_view   import RobotView
from ulsan_gui.views.log_view     import LogView
from ulsan_gui.views.settings_view import SettingsView

VIEWS = [
    ('map',      '🗺',  '지도'),
    ('robot',    '🤖',  '로봇'),
    ('log',      '📋',  '로그'),
    ('settings', '⚙',  '설정'),
]

PIN = '1234'

STATUS_STYLE = {
    'IDLE':      'color:#16a34a;',
    'BUSY':      'color:#d97706;',
    'RETURNING': 'color:#2563eb;',
    'WAITING':   'color:#9333ea;',
    'UNKNOWN':   'color:#9ca3af;',
}


class MainWindow(QMainWindow):
    def __init__(self, ros_node):
        super().__init__()
        self.ros = ros_node
        self.setWindowTitle('wego 관제 대시보드')
        self.resize(1280, 800)

        # ── 루트 레이아웃: 로그인 / 메인 앱 전환 ──
        self._root = QStackedWidget()
        self.setCentralWidget(self._root)

        self._login_view = LoginView(PIN, self._on_login_success)
        self._root.addWidget(self._login_view)

        self._main_widget = self._build_main()
        self._root.addWidget(self._main_widget)

        self._root.setCurrentWidget(self._login_view)

        # 헤더 시계
        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)

        # ROS 시그널 연결
        self.ros.signals.sig_status_1.connect(lambda s: self._update_status_badge('limo1', s))
        self.ros.signals.sig_status_2.connect(lambda s: self._update_status_badge('limo2', s))

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
        hbox.setContentsMargins(20, 0, 20, 0)

        logo = QLabel('🤖 wego')
        logo.setFont(QFont('Segoe UI', 14, QFont.Bold))
        logo.setStyleSheet('color:#1e40af;')
        hbox.addWidget(logo)

        hbox.addSpacing(20)

        self._badge_limo1 = QLabel('LIMO 1  UNKNOWN')
        self._badge_limo2 = QLabel('LIMO 2  UNKNOWN')
        for badge in (self._badge_limo1, self._badge_limo2):
            badge.setFont(QFont('Segoe UI', 10))
            badge.setStyleSheet(
                'background:#f1f5f9; border-radius:8px; padding:3px 10px;'
                + STATUS_STYLE['UNKNOWN']
            )
            hbox.addWidget(badge)
            hbox.addSpacing(8)

        hbox.addStretch(1)

        self._clock_label = QLabel('00:00:00')
        self._clock_label.setFont(QFont('Consolas', 11))
        self._clock_label.setStyleSheet('color:#374151;')
        hbox.addWidget(self._clock_label)

        hbox.addSpacing(16)

        logout_btn = QPushButton('로그아웃')
        logout_btn.setStyleSheet(
            'background:#f1f5f9; border:1px solid #d1d5db; border-radius:6px;'
            'padding:4px 12px; font-size:11px; color:#374151;'
        )
        logout_btn.clicked.connect(self._logout)
        hbox.addWidget(logout_btn)

        return header

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setFixedWidth(64)
        sidebar.setStyleSheet('background:#1e293b; border-right:1px solid #334155;')

        vbox = QVBoxLayout(sidebar)
        vbox.setContentsMargins(0, 12, 0, 12)
        vbox.setSpacing(4)
        vbox.setAlignment(Qt.AlignTop)

        self._sb_btns: dict[str, QPushButton] = {}
        for key, icon, tooltip in VIEWS:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            btn.setFixedSize(56, 52)
            btn.setFont(QFont('Segoe UI', 18))
            btn.setStyleSheet(self._sb_style(False))
            btn.clicked.connect(lambda _, k=key: self._switch_view(k))
            self._sb_btns[key] = btn
            vbox.addWidget(btn, alignment=Qt.AlignHCenter)

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
        if key == 'map':
            return MapView(self.ros)
        if key == 'robot':
            return RobotView(self.ros)
        if key == 'log':
            return LogView(self.ros)
        if key == 'settings':
            return SettingsView(self.ros)
        return QLabel(key)

    # ── 뷰 전환 ──────────────────────────────────────────────────────

    def _switch_view(self, key: str) -> None:
        self._stack.setCurrentWidget(self._views[key])
        for k, btn in self._sb_btns.items():
            btn.setStyleSheet(self._sb_style(k == key))

    @staticmethod
    def _sb_style(active: bool) -> str:
        if active:
            return 'background:#1e40af; color:#fff; border:none; border-radius:10px;'
        return 'background:transparent; color:#94a3b8; border:none; border-radius:10px;'

    # ── 로그인 / 로그아웃 ────────────────────────────────────────────

    def _on_login_success(self) -> None:
        self._root.setCurrentWidget(self._main_widget)

    def _logout(self) -> None:
        self._login_view.reset()
        self._root.setCurrentWidget(self._login_view)

    # ── 헤더 업데이트 ────────────────────────────────────────────────

    def _update_status_badge(self, robot: str, status: str) -> None:
        badge = self._badge_limo1 if robot == 'limo1' else self._badge_limo2
        name  = 'LIMO 1' if robot == 'limo1' else 'LIMO 2'
        badge.setText(f'{name}  {status}')
        badge.setStyleSheet(
            'background:#f1f5f9; border-radius:8px; padding:3px 10px;'
            + STATUS_STYLE.get(status, STATUS_STYLE['UNKNOWN'])
        )

    def _tick_clock(self) -> None:
        from datetime import datetime
        self._clock_label.setText(datetime.now().strftime('%H:%M:%S'))
