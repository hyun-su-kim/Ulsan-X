import math

import requests
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QImage, QPixmap, QPainter, QColor, QPen, QBrush

STATUS_COLOR = {
    'IDLE':      '#16a34a', 'BUSY':      '#d97706',
    'RETURNING': '#2563eb', 'WAITING':   '#9333ea', 'UNKNOWN': '#9ca3af',
}
STATUS_BG = {
    'IDLE':      '#f0fdf4', 'BUSY':      '#fffbeb',
    'RETURNING': '#eff6ff', 'WAITING':   '#faf5ff', 'UNKNOWN': '#f8fafc',
}
STATUS_BORDER = {
    'IDLE':      '#10b981', 'BUSY':      '#f59e0b',
    'RETURNING': '#3b82f6', 'WAITING':   '#9333ea', 'UNKNOWN': '#9ca3af',
}
# Domain ID 하드코딩 (LIMO1=6, LIMO2=7)
ROBOT_DOMAIN = {'limo1': 6, 'limo2': 7}

LOG_TYPE_COLOR = {
    'mission_start':    ('#dbeafe', '#1d4ed8'),
    'mission_complete': ('#d1fae5', '#047857'),
    'mission_fail':     ('#fee2e2', '#b91c1c'),
    'waiting':          ('#fef3c7', '#b45309'),
    'system':           ('#f3f4f6', '#374151'),
}

CARD_TITLE_STYLE = (
    'font-size:11px; font-weight:600; color:#6b7280;'
    'letter-spacing:0.5px; border:none;'
)

DEFAULT_DESTINATIONS = [
    ('목적지 선택...', None),
    ('classroom_1',            'classroom_1'),
    ('classroom_2',            'classroom_2'),
    ('classroom_3',            'classroom_3'),
    ('classroom_4',            'classroom_4'),
    ('classroom_5',            'classroom_5'),
    ('counseling_1',           'counseling_1'),
    ('counseling_2',           'counseling_2'),
    ('intensive_counseling_1', 'intensive_counseling_1'),
    ('intensive_counseling_2', 'intensive_counseling_2'),
    ('counter',                'counter'),
    ('home_robot1',            'home_robot1'),
    ('home_robot2',            'home_robot2'),
]


# ── FastAPI 비동기 체크 스레드 ────────────────────────────────────────

class _FastApiChecker(QThread):
    done = pyqtSignal(bool)

    def run(self) -> None:
        try:
            r = requests.get('http://localhost:8000/logs', timeout=0.5)
            self.done.emit(r.ok)
        except Exception:
            self.done.emit(False)


# ── 맵 캔버스 ────────────────────────────────────────────────────────

class MapCanvas(QWidget):
    """OccupancyGrid + 로봇 마커 + 범례 + 줌 컨트롤."""

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(
            'background:#f8fafc; border-radius:6px; border:1px solid #e5e7eb;'
        )
        self._map_pixmap: QPixmap | None = None
        self._map_info   = None
        self._poses: dict[str, tuple | None] = {'limo1': None, 'limo2': None}
        self._statuses: dict[str, str] = {'limo1': 'UNKNOWN', 'limo2': 'UNKNOWN'}
        self._robot_colors = {'limo1': QColor('#2563eb'), 'limo2': QColor('#d97706')}

        # ── 줌 컨트롤 (우하단 오버레이) ──
        ctrl_frame = QFrame(self)
        ctrl_frame.setStyleSheet(
            'background:transparent; border:none;'
        )
        ctrl_vbox = QVBoxLayout(ctrl_frame)
        ctrl_vbox.setContentsMargins(0, 0, 0, 0)
        ctrl_vbox.setSpacing(4)
        for sym in ('+', '−', '⟳'):
            b = QPushButton(sym)
            b.setFixedSize(28, 28)
            b.setFont(QFont('Segoe UI', 13))
            b.setFocusPolicy(Qt.NoFocus)
            b.setStyleSheet(
                'background:white; border:1px solid #d1d5db; border-radius:6px;'
                'color:#374151;'
            )
            ctrl_vbox.addWidget(b)
        self._ctrl_frame = ctrl_frame

        # ── 범례 (좌상단 오버레이) ──
        leg_frame = QFrame(self)
        leg_frame.setStyleSheet(
            'background:rgba(255,255,255,230); border-radius:8px; border:1px solid #e5e7eb;'
        )
        leg_vbox = QVBoxLayout(leg_frame)
        leg_vbox.setContentsMargins(8, 8, 10, 8)
        leg_vbox.setSpacing(4)

        self._legend_rows: dict[str, QLabel] = {}
        for robot_id, label, color in (
            ('limo1', 'LIMO 1 (UNKNOWN)', '#f59e0b'),
            ('limo2', 'LIMO 2 (UNKNOWN)', '#10b981'),
        ):
            row = QHBoxLayout()
            row.setSpacing(6)
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f'background:{color}; border-radius:5px; border:none;')
            row.addWidget(dot)
            lbl = QLabel(label)
            lbl.setFont(QFont('Segoe UI', 11))
            lbl.setStyleSheet('color:#374151; border:none; background:transparent;')
            row.addWidget(lbl)
            row.addStretch()
            leg_vbox.addLayout(row)
            self._legend_rows[robot_id] = lbl
        self._leg_frame = leg_frame

        QTimer.singleShot(0, self._reposition_overlays)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._reposition_overlays()

    def _reposition_overlays(self) -> None:
        if self._ctrl_frame:
            self._ctrl_frame.adjustSize()
            cw = self._ctrl_frame.sizeHint().width()
            ch = self._ctrl_frame.sizeHint().height()
            self._ctrl_frame.setGeometry(self.width() - cw - 12, self.height() - ch - 12, cw, ch)
        if self._leg_frame:
            self._leg_frame.adjustSize()
            lw = self._leg_frame.sizeHint().width()
            lh = self._leg_frame.sizeHint().height()
            self._leg_frame.setGeometry(10, 10, max(lw, 140), lh)

    def update_map(self, msg) -> None:
        info = msg.info
        w, h = info.width, info.height
        data = msg.data
        img = QImage(w, h, QImage.Format_RGB888)
        for y in range(h):
            for x in range(w):
                v = data[y * w + x]
                c = 200 if v == -1 else (255 if v == 0 else 0)
                img.setPixel(x, h - 1 - y, QColor(c, c, c).rgb())
        self._map_pixmap = QPixmap.fromImage(img)
        self._map_info   = info
        self.update()

    def update_pose(self, robot: str, msg) -> None:
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y ** 2 + q.z ** 2)
        )
        self._poses[robot] = (p.x, p.y, yaw)
        self.update()

    def update_status(self, robot: str, status: str) -> None:
        self._statuses[robot] = status
        lbl = self._legend_rows.get(robot)
        if lbl:
            name = 'LIMO 1' if robot == 'limo1' else 'LIMO 2'
            lbl.setText(f'{name} ({status})')

    def paintEvent(self, _) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self._map_pixmap is None:
            painter.setPen(QColor('#94a3b8'))
            painter.setFont(QFont('Segoe UI', 13))
            painter.drawText(self.rect(), Qt.AlignCenter, '/map 토픽 대기 중...')
            return

        info  = self._map_info
        scale = min(w / info.width, h / info.height)
        draw_w = int(info.width  * scale)
        draw_h = int(info.height * scale)
        off_x  = (w - draw_w) // 2
        off_y  = (h - draw_h) // 2
        painter.drawPixmap(off_x, off_y, draw_w, draw_h, self._map_pixmap)

        for robot, pose in self._poses.items():
            if pose is None:
                continue
            rx, ry, ryaw = pose
            px = off_x + int((rx - info.origin.position.x) / info.resolution * scale)
            py = off_y + draw_h - int((ry - info.origin.position.y) / info.resolution * scale)

            color = self._robot_colors[robot]
            painter.save()
            painter.translate(px, py)
            painter.rotate(-math.degrees(ryaw))
            painter.setPen(QPen(color, 2))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(-8, -8, 16, 16)
            painter.setPen(QPen(Qt.white, 2))
            painter.drawLine(0, 0, 0, -12)
            painter.restore()

            label = 'L1' if robot == 'limo1' else 'L2'
            painter.setPen(Qt.white)
            painter.setFont(QFont('Segoe UI', 8, QFont.Bold))
            painter.drawText(px + 10, py - 4, label)


# ── 로봇 상태 카드 ────────────────────────────────────────────────────

class RobotStatusCard(QFrame):
    def __init__(self, robot_id: str):
        super().__init__()
        self._robot_id = robot_id
        self._status   = 'UNKNOWN'
        domain = ROBOT_DOMAIN.get(robot_id, '?')
        self._domain_str = f'Domain {domain}'
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._build_ui()
        self._apply_border()

    def _build_ui(self) -> None:
        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(12, 10, 12, 10)
        hbox.setSpacing(10)

        self._avatar = QLabel('🤖')
        self._avatar.setFixedSize(38, 38)
        self._avatar.setAlignment(Qt.AlignCenter)
        self._avatar.setFont(QFont('Segoe UI', 18))
        self._avatar.setStyleSheet(
            f'border-radius:9px; background:{STATUS_BG["UNKNOWN"]}; border:none;'
        )
        hbox.addWidget(self._avatar)

        info_vbox = QVBoxLayout()
        info_vbox.setSpacing(2)
        info_vbox.setContentsMargins(0, 0, 0, 0)

        name = 'LIMO 1' if self._robot_id == 'limo1' else 'LIMO 2'
        name_lbl = QLabel(name)
        name_lbl.setFont(QFont('Segoe UI', 13, QFont.Bold))
        name_lbl.setStyleSheet('color:#111827; border:none;')

        self._dest_lbl = QLabel('방문자 대기 중')
        self._dest_lbl.setFont(QFont('Segoe UI', 11))
        self._dest_lbl.setStyleSheet('color:#6b7280; border:none;')

        self._sub_lbl = QLabel(f'{self._domain_str} · 배터리 -- %')
        self._sub_lbl.setFont(QFont('Segoe UI', 10))
        self._sub_lbl.setStyleSheet('color:#9ca3af; border:none;')

        info_vbox.addWidget(name_lbl)
        info_vbox.addWidget(self._dest_lbl)
        info_vbox.addWidget(self._sub_lbl)
        hbox.addLayout(info_vbox, 1)

        self._badge = QLabel('UNKNOWN')
        self._badge.setFont(QFont('Segoe UI', 10, QFont.Bold))
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setStyleSheet(
            f'border-radius:12px; padding:3px 8px; border:none;'
            f'color:{STATUS_COLOR["UNKNOWN"]}; background:{STATUS_BG["UNKNOWN"]};'
        )
        hbox.addWidget(self._badge)

    def _apply_border(self) -> None:
        border = STATUS_BORDER.get(self._status, STATUS_BORDER['UNKNOWN'])
        bg     = STATUS_BG.get(self._status, STATUS_BG['UNKNOWN'])
        # Qt에서 border 단축형 후 border-left 오버라이드가 불안정하므로 4방향 개별 지정
        self.setStyleSheet(
            f'background:#fff; border-radius:10px;'
            f'border-top:1px solid #e5e7eb;'
            f'border-right:1px solid #e5e7eb;'
            f'border-bottom:1px solid #e5e7eb;'
            f'border-left:4px solid {border};'
        )
        self._avatar.setStyleSheet(
            f'border-radius:9px; background:{bg}; border:none;'
        )

    def update_status(self, status: str) -> None:
        self._status = status
        self._apply_border()
        c  = STATUS_COLOR.get(status, STATUS_COLOR['UNKNOWN'])
        bg = STATUS_BG.get(status, STATUS_BG['UNKNOWN'])
        self._badge.setText(status)
        self._badge.setStyleSheet(
            f'border-radius:12px; padding:3px 8px; border:none;'
            f'color:{c}; background:{bg};'
        )
        if status == 'IDLE':
            self._dest_lbl.setText('방문자 대기 중')

    def update_destination(self, dest: str) -> None:
        if dest:
            self._dest_lbl.setText(f'→ {dest}')



# ── 미니 로그 fetch 스레드 ────────────────────────────────────────────

class _LogFetch(QThread):
    done = pyqtSignal(list)

    def run(self) -> None:
        try:
            r = requests.get('http://localhost:8000/logs', timeout=2)
            if r.ok:
                self.done.emit(r.json()[-8:])
        except Exception:
            pass


# ── 미니 미션 로그 카드 ───────────────────────────────────────────────

class MiniLogCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet('background:#fff; border-radius:10px; border:1px solid #e5e7eb;')
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(14, 12, 14, 10)
        vbox.setSpacing(6)

        title = QLabel('📋 미션 로그')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(CARD_TITLE_STYLE)
        vbox.addWidget(title)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(['시각', '로봇', '내용', '유형'])
        self._table.horizontalHeader().setFont(QFont('Segoe UI', 9, QFont.Bold))
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.setFont(QFont('Segoe UI', 9))
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setDefaultSectionSize(22)
        self._table.setStyleSheet(
            'QTableWidget { border:none; background:#fff; }'
            'QHeaderView::section { background:#f8fafc; border:none;'
            '  border-bottom:1px solid #e5e7eb; padding:3px; }'
            'QTableWidget::item { padding:2px 4px; }'
        )
        vbox.addWidget(self._table, 1)

        timer = QTimer(self)
        timer.timeout.connect(self._fetch)
        timer.start(5000)
        self._fetch()

    def _fetch(self) -> None:
        self._thread = _LogFetch()
        self._thread.done.connect(self._render)
        self._thread.start()

    def _render(self, logs: list) -> None:
        self._table.setRowCount(len(logs))
        for row, log in enumerate(logs):
            ts  = log.get('timestamp', '')
            ts  = ts[-8:] if len(ts) >= 8 else ts
            bot = log.get('robot', '').upper()
            msg = log.get('message', '')
            typ = log.get('type', 'system')
            bg, fg = LOG_TYPE_COLOR.get(typ, ('#fff', '#374151'))
            for col, text in enumerate([ts, bot, msg, typ]):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(fg))
                item.setBackground(QColor(bg))
                self._table.setItem(row, col, item)


# ── 메인 뷰 ──────────────────────────────────────────────────────────

class MapView(QWidget):
    def __init__(self, ros_node):
        super().__init__()
        self.setStyleSheet('background:#f0f2f5;')
        self.ros = ros_node
        self._selected_robot = 'limo1'
        self._build_ui()
        self._connect_signals()

        self._conn_timer = QTimer()
        self._conn_timer.timeout.connect(self._check_connections)
        self._conn_timer.start(2000)

    def _build_ui(self) -> None:
        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(10, 10, 10, 10)
        hbox.setSpacing(10)

        # ── 좌열 (260px): 로봇 카드 + 미니 로그 ──
        left = QWidget()
        left.setFixedWidth(260)
        left_vbox = QVBoxLayout(left)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(8)

        # 로봇 카드 (168px — 목업 grid-template-rows:168px)
        cards_area = QWidget()
        cards_area.setFixedHeight(168)
        cards_vbox = QVBoxLayout(cards_area)
        cards_vbox.setContentsMargins(0, 0, 0, 0)
        cards_vbox.setSpacing(8)
        self._card1 = RobotStatusCard('limo1')
        self._card2 = RobotStatusCard('limo2')
        cards_vbox.addWidget(self._card1)
        cards_vbox.addWidget(self._card2)
        left_vbox.addWidget(cards_area)

        # 미니 로그 (나머지 공간)
        self._mini_log = MiniLogCard()
        left_vbox.addWidget(self._mini_log, 1)
        hbox.addWidget(left)

        # ── 중앙: 지도 패널 (카드 + 타이틀 + 캔버스) ──
        map_card = QFrame()
        map_card.setStyleSheet('background:#fff; border-radius:10px; border:1px solid #e5e7eb;')
        map_card_vbox = QVBoxLayout(map_card)
        map_card_vbox.setContentsMargins(14, 12, 14, 14)
        map_card_vbox.setSpacing(8)

        map_title = QLabel('🗺  실시간 위치 — /map OccupancyGrid')
        map_title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        map_title.setStyleSheet(CARD_TITLE_STYLE)
        map_card_vbox.addWidget(map_title)

        self._canvas = MapCanvas()
        map_card_vbox.addWidget(self._canvas, 1)
        hbox.addWidget(map_card, 1)

        # ── 우열 (260px): 제어 패널 ──
        right = QWidget()
        right.setFixedWidth(260)
        right_vbox = QVBoxLayout(right)
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(8)
        right_vbox.addWidget(self._build_mission_card())
        right_vbox.addWidget(self._build_emergency_card())
        right_vbox.addWidget(self._build_sys_card(), 1)
        hbox.addWidget(right)

    def _build_mission_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet('background:#fff; border-radius:10px; border:1px solid #e5e7eb;')
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(8)

        title = QLabel('🎯  수동 임무 발행')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(CARD_TITLE_STYLE)
        vbox.addWidget(title)

        # 로봇 토글 버튼 (목업의 .rsel-btn)
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(6)
        self._rsel_btns: dict[str, QPushButton] = {}
        for robot_id, label in (('limo1', 'LIMO 1'), ('limo2', 'LIMO 2')):
            btn = QPushButton(label)
            btn.setFont(QFont('Segoe UI', 11, QFont.Bold))
            btn.setFixedHeight(32)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet(self._rsel_style(robot_id == 'limo1'))
            btn.clicked.connect(lambda _, r=robot_id: self._select_robot(r))
            self._rsel_btns[robot_id] = btn
            toggle_row.addWidget(btn)
        vbox.addLayout(toggle_row)

        self._dest_combo = QComboBox()
        self._dest_combo.setFont(QFont('Segoe UI', 11))
        self._dest_combo.setStyleSheet(
            'border:1px solid #d1d5db; border-radius:6px; padding:5px 8px;'
            'background:#f9fafb; color:#374151;'
        )
        for label, key in DEFAULT_DESTINATIONS:
            self._dest_combo.addItem(label, userData=key)
        vbox.addWidget(self._dest_combo)

        send_btn = QPushButton('📤  goal_destination 발행')
        send_btn.setFont(QFont('Segoe UI', 11, QFont.Bold))
        send_btn.setFixedHeight(34)
        send_btn.setFocusPolicy(Qt.NoFocus)
        send_btn.setStyleSheet(
            'background:#1e40af; color:#fff; border-radius:6px; border:none;'
        )
        send_btn.clicked.connect(self._send_mission)
        vbox.addWidget(send_btn)
        return card

    def _build_emergency_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet('background:#fff; border-radius:10px; border:1px solid #e5e7eb;')
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(8)

        title = QLabel('⚠️  긴급 제어')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(CARD_TITLE_STYLE)
        vbox.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(6)
        pause_btn = QPushButton('⏸ 일시정지')
        pause_btn.setFixedHeight(34)
        pause_btn.setFont(QFont('Segoe UI', 11, QFont.Bold))
        pause_btn.setFocusPolicy(Qt.NoFocus)
        pause_btn.setStyleSheet(
            'background:#fef3c7; color:#b45309;'
            'border:1.5px solid #fcd34d; border-radius:6px;'
        )
        pause_btn.clicked.connect(self._send_zero_vel)
        row.addWidget(pause_btn)

        stop_btn = QPushButton('🛑 임무중단')
        stop_btn.setFixedHeight(34)
        stop_btn.setFont(QFont('Segoe UI', 11, QFont.Bold))
        stop_btn.setFocusPolicy(Qt.NoFocus)
        stop_btn.setStyleSheet(
            'background:#fee2e2; color:#b91c1c;'
            'border:1.5px solid #fca5a5; border-radius:6px;'
        )
        stop_btn.clicked.connect(self._send_zero_vel)
        row.addWidget(stop_btn)
        vbox.addLayout(row)
        return card

    def _build_sys_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet('background:#fff; border-radius:10px; border:1px solid #e5e7eb;')
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(0)

        title = QLabel('📡  시스템 상태')
        title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        title.setStyleSheet(CARD_TITLE_STYLE)
        vbox.addWidget(title)
        vbox.addSpacing(6)

        self._sys_vals: dict[str, QLabel] = {}
        rows = [
            ('limo1_conn', 'LIMO 1 연결',    f'● Domain {ROBOT_DOMAIN["limo1"]} 대기', '#9ca3af'),
            ('limo2_conn', 'LIMO 2 연결',    f'● Domain {ROBOT_DOMAIN["limo2"]} 대기', '#9ca3af'),
            ('fastapi',    'FastAPI 서버',    '● 확인 중', '#9ca3af'),
            ('dispatcher', 'wego_dispatcher', '● 확인 중', '#9ca3af'),
            ('traffic',    '충돌 방지',       '● 확인 중', '#9ca3af'),
        ]
        for key, label, init_txt, init_color in rows:
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet('border:none; border-top:1px solid #f3f4f6;')
            vbox.addWidget(sep)

            row_w = QWidget()
            rh = QHBoxLayout(row_w)
            rh.setContentsMargins(0, 6, 0, 6)

            lbl = QLabel(label)
            lbl.setFont(QFont('Segoe UI', 11))
            lbl.setStyleSheet('color:#6b7280; border:none;')
            rh.addWidget(lbl)
            rh.addStretch()

            val = QLabel(init_txt)
            val.setFont(QFont('Segoe UI', 11, QFont.Bold))
            val.setStyleSheet(f'color:{init_color}; border:none;')
            rh.addWidget(val)

            self._sys_vals[key] = val
            vbox.addWidget(row_w)

        vbox.addStretch()
        return card

    # ── 시그널 연결 ───────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.ros.signals.sig_status_1.connect(
            lambda s: (self._card1.update_status(s), self._canvas.update_status('limo1', s)))
        self.ros.signals.sig_status_2.connect(
            lambda s: (self._card2.update_status(s), self._canvas.update_status('limo2', s)))
        self.ros.signals.sig_pose_1.connect(lambda m: self._canvas.update_pose('limo1', m))
        self.ros.signals.sig_pose_2.connect(lambda m: self._canvas.update_pose('limo2', m))
        self.ros.signals.sig_map.connect(self._canvas.update_map)
        self.ros.signals.sig_dest_1.connect(self._card1.update_destination)
        self.ros.signals.sig_dest_2.connect(self._card2.update_destination)

    # ── 동작 ─────────────────────────────────────────────────────────

    def _select_robot(self, robot: str) -> None:
        self._selected_robot = robot
        for r, btn in self._rsel_btns.items():
            btn.setStyleSheet(self._rsel_style(r == robot))

    def _send_mission(self) -> None:
        key = self._dest_combo.currentData()
        if key:
            self.ros.publish_goal(self._selected_robot, key)

    def _send_zero_vel(self) -> None:
        for robot in ('limo1', 'limo2'):
            self.ros.publish_cmd_vel(robot, 0.0, 0.0)

    def _check_connections(self) -> None:
        # limo 연결 상태
        for robot, key in (('limo1', 'limo1_conn'), ('limo2', 'limo2_conn')):
            conn   = self.ros.is_connected(robot)
            val    = self._sys_vals[key]
            domain = ROBOT_DOMAIN[robot]
            if conn:
                val.setText(f'● Domain {domain} 정상')
                val.setStyleSheet('color:#059669; border:none;')
            else:
                val.setText(f'● Domain {domain} 끊김')
                val.setStyleSheet('color:#ef4444; border:none;')

        # FastAPI 비동기 핑
        if not hasattr(self, '_api_checker') or not self._api_checker.isRunning():
            self._api_checker = _FastApiChecker()
            self._api_checker.done.connect(self._on_fastapi_result)
            self._api_checker.start()

        # ROS 노드 목록으로 dispatcher / traffic 체크
        try:
            node_names = self.ros.get_node_names()
            for key, node_name in (
                ('dispatcher', 'wego_dispatcher'),
                ('traffic',    'wego_traffic'),
            ):
                val = self._sys_vals[key]
                if node_name in node_names:
                    val.setText(f'● {node_name} 실행 중')
                    val.setStyleSheet('color:#059669; border:none;')
                else:
                    val.setText(f'● {node_name} 미실행')
                    val.setStyleSheet('color:#ef4444; border:none;')
        except Exception:
            pass

    def _on_fastapi_result(self, ok: bool) -> None:
        val = self._sys_vals['fastapi']
        if ok:
            val.setText('● 응답 정상')
            val.setStyleSheet('color:#059669; border:none;')
        else:
            val.setText('● 응답 없음')
            val.setStyleSheet('color:#ef4444; border:none;')

    @staticmethod
    def _rsel_style(active: bool) -> str:
        if active:
            return ('background:#eff6ff; color:#1e40af; border:1.5px solid #1e40af;'
                    'border-radius:6px; padding:4px;')
        return ('background:#f9fafb; color:#374151; border:1.5px solid #e5e7eb;'
                'border-radius:6px; padding:4px;')
