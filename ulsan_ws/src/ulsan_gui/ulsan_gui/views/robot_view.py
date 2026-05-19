import math

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QSlider, QFrame, QSizePolicy,
    QDialog, QScrollArea,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QImage, QPixmap, QKeyEvent

STATUS_COLOR = {
    'IDLE':      '#16a34a', 'BUSY': '#d97706',
    'RETURNING': '#2563eb', 'WAITING': '#9333ea', 'UNKNOWN': '#9ca3af',
}
STATUS_BG = {
    'IDLE':      '#f0fdf4', 'BUSY': '#fffbeb',
    'RETURNING': '#eff6ff', 'WAITING': '#faf5ff', 'UNKNOWN': '#f8fafc',
}

TELEOP_KEYS = {
    Qt.Key_I:     (1,  0),   # 전진
    Qt.Key_K:     (0,  0),   # 정지
    Qt.Key_Comma: (-1, 0),   # 후진  (,)
    Qt.Key_J:     (0,  1),   # 좌회전
    Qt.Key_L:     (0, -1),   # 우회전
    Qt.Key_U:     (1,  1),   # 전진+좌
    Qt.Key_O:     (1, -1),   # 전진+우
    Qt.Key_M:     (-1, 1),   # 후진+좌
    Qt.Key_Period:(-1,-1),   # 후진+우  (.)
    Qt.Key_Space: (0,  0),   # 정지
    Qt.Key_Up:    (1,  0),
    Qt.Key_Down:  (-1, 0),
    Qt.Key_Left:  (0,  1),
    Qt.Key_Right: (0, -1),
}

CARD_STYLE  = 'background:#fff; border-radius:10px; border:1px solid #e5e7eb;'
LABEL_STYLE = 'color:#111827; border:none;'


class CameraWidget(QLabel):
    """CompressedImage → QPixmap 표시. 전체화면 버튼 포함."""

    def __init__(self, robot: str, ros_node):
        super().__init__()
        self.robot = robot
        self.ros   = ros_node
        self._raw_bytes: bytes | None = None
        self._fmt: str = ''

        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet('background:#0d1117; border-radius:8px; border:none;')
        self.setAlignment(Qt.AlignCenter)
        self.setText('카메라 신호 없음')
        self.setFont(QFont('Segoe UI', 10))
        self.setStyleSheet('background:#0d1117; border-radius:8px; border:none; color:#4b5563;')

    def update_image(self, data: bytes, fmt: str) -> None:
        self._raw_bytes = data
        self._fmt = fmt
        img = QImage.fromData(data)
        if not img.isNull():
            pix = QPixmap.fromImage(img).scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.setPixmap(pix)

    def resizeEvent(self, _) -> None:
        if self._raw_bytes:
            self.update_image(self._raw_bytes, self._fmt)

    def open_fullscreen(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(f'{self.robot.upper()} 전방 카메라')
        dlg.showFullScreen()
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)

        cam = QLabel()
        cam.setAlignment(Qt.AlignCenter)
        cam.setStyleSheet('background:#000;')
        layout.addWidget(cam)

        close_btn = QPushButton('닫기  [Esc]')
        close_btn.setFixedHeight(36)
        close_btn.setStyleSheet('background:#374151; color:#fff; border:none; font-size:12px;')
        close_btn.clicked.connect(dlg.close)
        layout.addWidget(close_btn)

        def _refresh():
            if self._raw_bytes:
                img = QImage.fromData(self._raw_bytes)
                if not img.isNull():
                    pix = QPixmap.fromImage(img).scaled(
                        cam.width(), cam.height(),
                        Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    cam.setPixmap(pix)

        timer = QTimer(dlg)
        timer.timeout.connect(_refresh)
        timer.start(33)

        dlg.keyPressEvent = lambda e: dlg.close() if e.key() == Qt.Key_Escape else None
        dlg.exec_()


class TeleopCard(QFrame):
    """D-pad + 키보드 텔레옵. i/j/k/l/, 및 화살표 지원."""

    LINEAR_SPEED  = 0.3
    ANGULAR_SPEED = 0.5

    def __init__(self, robot: str, ros_node):
        super().__init__()
        self.robot = robot
        self.ros   = ros_node
        self._speed_scale = 1.0
        self.setStyleSheet(CARD_STYLE)
        self.setFocusPolicy(Qt.StrongFocus)
        self._build_ui()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(10)

        title = QLabel(f'🕹 수동 조작  {self.robot.upper()}')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(LABEL_STYLE)
        vbox.addWidget(title)

        sub = QLabel('/cmd_vel  ·  i j k l ,  /  방향키')
        sub.setFont(QFont('Segoe UI', 9))
        sub.setStyleSheet('color:#9ca3af; border:none;')
        vbox.addWidget(sub)

        # D-pad
        grid = [
            ['',  '▲',  ''],
            ['◀', '■',  '▶'],
            ['',  '▼',  ''],
        ]
        acts = [
            [None,    (1,0),  None   ],
            [(0,1),   (0,0),  (0,-1) ],
            [None,    (-1,0), None   ],
        ]
        dpad_widget = QWidget()
        dpad_layout = QVBoxLayout(dpad_widget)
        dpad_layout.setSpacing(4)
        dpad_layout.setContentsMargins(0, 0, 0, 0)
        for r_idx, row in enumerate(grid):
            row_w = QHBoxLayout()
            row_w.setSpacing(4)
            for c_idx, sym in enumerate(row):
                btn = QPushButton(sym)
                btn.setFixedSize(40, 40)
                btn.setFont(QFont('Segoe UI', 14))
                if sym == '':
                    btn.setEnabled(False)
                    btn.setStyleSheet('background:transparent; border:none;')
                else:
                    btn.setStyleSheet(
                        'background:#f3f4f6; border:1px solid #d1d5db;'
                        'border-radius:7px; color:#374151;'
                    )
                    act = acts[r_idx][c_idx]
                    if act:
                        btn.pressed.connect(
                            lambda lin=act[0], ang=act[1]: self._send(lin, ang))
                        btn.released.connect(lambda: self._send(0, 0))
                row_w.addWidget(btn)
            dpad_layout.addLayout(row_w)
        vbox.addWidget(dpad_widget, alignment=Qt.AlignHCenter)

        # 속도 슬라이더
        speed_row = QHBoxLayout()
        speed_lbl = QLabel('속도')
        speed_lbl.setFont(QFont('Segoe UI', 10))
        speed_lbl.setStyleSheet('color:#6b7280; border:none;')

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(1, 10)
        self._slider.setValue(3)
        self._slider.valueChanged.connect(self._on_speed_change)

        self._speed_val_lbl = QLabel('0.3 m/s')
        self._speed_val_lbl.setFont(QFont('Segoe UI', 10))
        self._speed_val_lbl.setStyleSheet('color:#374151; border:none;')

        speed_row.addWidget(speed_lbl)
        speed_row.addWidget(self._slider, 1)
        speed_row.addWidget(self._speed_val_lbl)
        vbox.addLayout(speed_row)

    def _on_speed_change(self, val: int) -> None:
        self._speed_scale = val / 10.0
        self._speed_val_lbl.setText(f'{self._speed_scale:.1f} m/s')

    def _send(self, lin: int, ang: int) -> None:
        self.ros.publish_cmd_vel(
            self.robot,
            lin * self.LINEAR_SPEED  * self._speed_scale,
            ang * self.ANGULAR_SPEED * self._speed_scale,
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        act = TELEOP_KEYS.get(event.key())
        if act:
            self._send(act[0], act[1])
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        if event.key() in TELEOP_KEYS and event.key() not in (Qt.Key_K, Qt.Key_Space):
            self._send(0, 0)
        else:
            super().keyReleaseEvent(event)


class RobotPanel(QWidget):
    """단일 로봇 상세 패널: 정보(1) | 카메라(3) | 텔레옵(1)"""

    def __init__(self, robot: str, ros_node):
        super().__init__()
        self.robot = robot
        self.ros   = ros_node
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        main_vbox = QVBoxLayout(self)
        main_vbox.setContentsMargins(10, 10, 10, 10)
        main_vbox.setSpacing(10)

        # 상단: 정보(1) | 카메라(3) | 텔레옵(1)
        top = QHBoxLayout()
        top.setSpacing(10)

        top.addWidget(self._build_info_card(), 1)
        top.addWidget(self._build_camera_card(), 3)
        top.addWidget(self._build_teleop_card(), 1)

        main_vbox.addLayout(top, 1)

        # 하단: 연결 상태 바
        self._conn_bar = self._build_conn_bar()
        main_vbox.addWidget(self._conn_bar)

    def _build_info_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(6)

        # 헤더
        name_lbl = QLabel(f'🤖 {self.robot.upper()}')
        name_lbl.setFont(QFont('Segoe UI', 13, QFont.Bold))
        name_lbl.setStyleSheet(LABEL_STYLE)
        vbox.addWidget(name_lbl)

        self._status_badge = QLabel('UNKNOWN')
        self._status_badge.setFont(QFont('Segoe UI', 10, QFont.Bold))
        self._status_badge.setStyleSheet(
            'border-radius:8px; padding:3px 10px; border:none;'
            f'color:{STATUS_COLOR["UNKNOWN"]}; background:{STATUS_BG["UNKNOWN"]};'
        )
        vbox.addWidget(self._status_badge)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('color:#e5e7eb; border:none; border-top:1px solid #e5e7eb;')
        vbox.addWidget(sep)

        # 메트릭
        metrics = [
            ('배터리',   '--',  '%'),
            ('금일 임무', '--', '건'),
            ('가동 시간', '--', ''),
        ]
        self._metric_vals: dict[str, QLabel] = {}
        for label, init_val, unit in metrics:
            row = QHBoxLayout()
            k = QLabel(label)
            k.setFont(QFont('Segoe UI', 10))
            k.setStyleSheet('color:#6b7280; border:none;')

            v = QLabel(f'{init_val} {unit}'.strip())
            v.setFont(QFont('Segoe UI', 10, QFont.Bold))
            v.setStyleSheet('color:#111827; border:none;')
            self._metric_vals[label] = v

            row.addWidget(k)
            row.addStretch()
            row.addWidget(v)
            vbox.addLayout(row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet('color:#e5e7eb; border:none; border-top:1px solid #e5e7eb;')
        vbox.addWidget(sep2)

        # 이벤트 목록 (스크롤)
        evt_title = QLabel('⚡ 이벤트')
        evt_title.setFont(QFont('Segoe UI', 10, QFont.Bold))
        evt_title.setStyleSheet(LABEL_STYLE)
        vbox.addWidget(evt_title)

        self._evt_area = QScrollArea()
        self._evt_area.setWidgetResizable(True)
        self._evt_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._evt_area.setStyleSheet('border:none; background:transparent;')

        self._evt_container = QWidget()
        self._evt_layout = QVBoxLayout(self._evt_container)
        self._evt_layout.setContentsMargins(0, 0, 0, 0)
        self._evt_layout.setSpacing(2)
        self._evt_layout.addStretch()
        self._evt_area.setWidget(self._evt_container)
        vbox.addWidget(self._evt_area, 1)

        return card

    def _build_camera_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(12, 10, 12, 10)
        vbox.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel(f'📷 {self.robot.upper()} 전방 카메라')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(LABEL_STYLE)
        header.addWidget(title)

        live_badge = QLabel('LIVE')
        live_badge.setFont(QFont('Segoe UI', 9, QFont.Bold))
        live_badge.setStyleSheet(
            'background:#ef4444; color:#fff; border-radius:4px;'
            'padding:1px 6px; border:none;'
        )
        header.addWidget(live_badge)
        header.addStretch()

        fs_btn = QPushButton('⛶ 전체화면')
        fs_btn.setFont(QFont('Segoe UI', 9))
        fs_btn.setStyleSheet(
            'background:#f1f5f9; border:1px solid #d1d5db; border-radius:6px;'
            'padding:3px 10px; color:#374151;'
        )
        header.addWidget(fs_btn)
        vbox.addLayout(header)

        self._camera = CameraWidget(self.robot, self.ros)
        vbox.addWidget(self._camera, 1)

        fs_btn.clicked.connect(self._camera.open_fullscreen)

        return card

    def _build_teleop_card(self) -> TeleopCard:
        self._teleop = TeleopCard(self.robot, self.ros)
        return self._teleop

    def _build_conn_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(36)
        bar.setStyleSheet('background:#fff; border-radius:8px; border:1px solid #e5e7eb;')

        hbox = QHBoxLayout(bar)
        hbox.setContentsMargins(14, 0, 14, 0)

        self._conn_label = QLabel('● 연결 대기 중')
        self._conn_label.setFont(QFont('Segoe UI', 10))
        self._conn_label.setStyleSheet('color:#9ca3af; border:none;')
        hbox.addWidget(self._conn_label)
        hbox.addStretch()

        self._pose_label = QLabel('x: --  y: --  yaw: --°')
        self._pose_label.setFont(QFont('Consolas', 10))
        self._pose_label.setStyleSheet('color:#6b7280; border:none;')
        hbox.addWidget(self._pose_label)

        return bar

    # ── 시그널 연결 ───────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        if self.robot == 'limo1':
            self.ros.signals.sig_status_1.connect(self._on_status)
            self.ros.signals.sig_pose_1.connect(self._on_pose)
            self.ros.signals.sig_camera_1.connect(self._camera.update_image)
        else:
            self.ros.signals.sig_status_2.connect(self._on_status)
            self.ros.signals.sig_pose_2.connect(self._on_pose)
            self.ros.signals.sig_camera_2.connect(self._camera.update_image)

        # 연결 체크 타이머
        timer = QTimer(self)
        timer.timeout.connect(self._check_conn)
        timer.start(2000)

    def _on_status(self, status: str) -> None:
        self._status_badge.setText(status)
        c  = STATUS_COLOR.get(status, STATUS_COLOR['UNKNOWN'])
        bg = STATUS_BG.get(status, STATUS_BG['UNKNOWN'])
        self._status_badge.setStyleSheet(
            f'border-radius:8px; padding:3px 10px; border:none; color:{c}; background:{bg};'
        )
        self._add_event(status)

    def _on_pose(self, msg) -> None:
        x, y, yaw = self.ros.pose_to_xyyaw(msg)
        self._pose_label.setText(f'x: {x:.2f}  y: {y:.2f}  yaw: {math.degrees(yaw):.1f}°')

    def _add_event(self, msg: str) -> None:
        from datetime import datetime
        lbl = QLabel(f'{datetime.now().strftime("%H:%M:%S")}  {msg}')
        lbl.setFont(QFont('Segoe UI', 9))
        lbl.setStyleSheet('color:#374151; border:none; padding:2px 0;')
        # stretch 앞에 삽입
        self._evt_layout.insertWidget(self._evt_layout.count() - 1, lbl)
        # 최근 50개만 유지
        while self._evt_layout.count() > 51:
            item = self._evt_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._evt_area.verticalScrollBar().setValue(
            self._evt_area.verticalScrollBar().maximum()
        )

    def _check_conn(self) -> None:
        conn = self.ros.is_connected(self.robot)
        if conn:
            self._conn_label.setText('● 연결됨')
            self._conn_label.setStyleSheet('color:#16a34a; border:none;')
        else:
            self._conn_label.setText('● 연결 끊김')
            self._conn_label.setStyleSheet('color:#ef4444; border:none;')

    # ── 텔레옵 키 포커스 ─────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self._teleop.keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        self._teleop.keyReleaseEvent(event)


class RobotView(QWidget):
    """LIMO 1 / LIMO 2 탭 선택 뷰."""

    def __init__(self, ros_node):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self._build_ui(ros_node)

    def _build_ui(self, ros_node) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # 탭 바
        tab_bar = QFrame()
        tab_bar.setFixedHeight(48)
        tab_bar.setStyleSheet('background:#f8fafc; border-bottom:1px solid #e5e7eb;')
        tab_hbox = QHBoxLayout(tab_bar)
        tab_hbox.setContentsMargins(12, 6, 12, 6)
        tab_hbox.setSpacing(8)

        self._panels: dict[str, RobotPanel] = {}
        self._tab_btns: dict[str, QPushButton] = {}

        for robot in ('limo1', 'limo2'):
            label = 'LIMO 1' if robot == 'limo1' else 'LIMO 2'
            btn = QPushButton(f'🤖 {label}')
            btn.setFont(QFont('Segoe UI', 11, QFont.Bold))
            btn.setFixedHeight(36)
            btn.setStyleSheet(self._tab_style(False))
            btn.clicked.connect(lambda _, r=robot: self._select(r))
            self._tab_btns[robot] = btn
            tab_hbox.addWidget(btn)
            self._panels[robot] = RobotPanel(robot, ros_node)

        tab_hbox.addStretch()
        vbox.addWidget(tab_bar)

        # 패널 스택
        from PyQt5.QtWidgets import QStackedWidget
        self._stack = QStackedWidget()
        for panel in self._panels.values():
            self._stack.addWidget(panel)
        vbox.addWidget(self._stack, 1)

        self._select('limo1')

    def _select(self, robot: str) -> None:
        self._stack.setCurrentWidget(self._panels[robot])
        for r, btn in self._tab_btns.items():
            btn.setStyleSheet(self._tab_style(r == robot))
        self._panels[robot].setFocus()

    @staticmethod
    def _tab_style(active: bool) -> str:
        if active:
            return (
                'background:#eff6ff; color:#1e40af; border:2px solid #1e40af;'
                'border-radius:8px; padding:4px 16px;'
            )
        return (
            'background:#fff; color:#6b7280; border:2px solid #e5e7eb;'
            'border-radius:8px; padding:4px 16px;'
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        current = self._stack.currentWidget()
        if isinstance(current, RobotPanel):
            current.keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        current = self._stack.currentWidget()
        if isinstance(current, RobotPanel):
            current.keyReleaseEvent(event)
