import json
import math

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog,
    QDoubleSpinBox, QSlider, QSizePolicy, QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QKeyEvent

from ulsan_gui.views.robot_view import TELEOP_KEYS

CARD_STYLE  = 'background:#fff; border-radius:10px; border:1px solid #e5e7eb;'
LABEL_STYLE = 'color:#111827; border:none;'

WP_COLUMNS = ['key', '이름(label)', 'x', 'y', 'yaw (rad)']


class WaypointEditDialog(QDialog):
    """Waypoint 추가/수정 모달. 텔레옵 + 현재위치 적용 포함."""

    LINEAR_SPEED  = 0.3
    ANGULAR_SPEED = 0.5

    def __init__(self, parent, ros_node, robot: str,
                 key: str = '', label: str = '',
                 x: float = 0.0, y: float = 0.0, yaw: float = 0.0):
        super().__init__(parent)
        self.ros    = ros_node
        self.robot  = robot
        self._orig_key = key
        self._speed_scale = 0.3

        self.setWindowTitle('Waypoint 편집')
        self.setModal(True)
        self.resize(640, 460)
        self.setStyleSheet('background:#f0f2f5;')
        self.setFocusPolicy(Qt.StrongFocus)

        main = QHBoxLayout(self)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(14)

        # ── 좌: 입력 폼 ──
        form = QFrame()
        form.setStyleSheet(CARD_STYLE)
        form_vbox = QVBoxLayout(form)
        form_vbox.setContentsMargins(16, 16, 16, 16)
        form_vbox.setSpacing(10)

        def _field(lbl_text: str, init: str = '') -> QLineEdit:
            lbl = QLabel(lbl_text)
            lbl.setFont(QFont('Segoe UI', 10))
            lbl.setStyleSheet('color:#6b7280; border:none;')
            form_vbox.addWidget(lbl)
            field = QLineEdit(init)
            field.setStyleSheet('border:1px solid #d1d5db; border-radius:6px; padding:6px;')
            form_vbox.addWidget(field)
            return field

        self._key_field   = _field('key (식별자)',   key)
        self._label_field = _field('이름 (label)',   label)

        # x / y / yaw 숫자 스핀박스
        for name, val in (('x', x), ('y', y), ('yaw (rad)', yaw)):
            lbl = QLabel(name)
            lbl.setFont(QFont('Segoe UI', 10))
            lbl.setStyleSheet('color:#6b7280; border:none;')
            form_vbox.addWidget(lbl)
            spin = QDoubleSpinBox()
            spin.setRange(-999.0, 999.0)
            spin.setDecimals(4)
            spin.setSingleStep(0.01)
            spin.setValue(val)
            spin.setStyleSheet('border:1px solid #d1d5db; border-radius:6px; padding:4px;')
            form_vbox.addWidget(spin)
            setattr(self, f'_{name.split()[0]}_spin', spin)

        apply_btn = QPushButton('📍 현재 위치 적용')
        apply_btn.setStyleSheet(
            'background:#eff6ff; color:#1e40af; border:1px solid #bfdbfe;'
            'border-radius:6px; padding:7px;'
        )
        apply_btn.clicked.connect(self._apply_pose)
        form_vbox.addWidget(apply_btn)

        form_vbox.addStretch()
        main.addWidget(form, 1)

        # ── 우: 텔레옵 ──
        teleop = QFrame()
        teleop.setStyleSheet(CARD_STYLE)
        tele_vbox = QVBoxLayout(teleop)
        tele_vbox.setContentsMargins(14, 14, 14, 14)
        tele_vbox.setSpacing(10)

        t_title = QLabel(f'🕹 수동 조작  {robot.upper()}')
        t_title.setFont(QFont('Segoe UI', 11, QFont.Bold))
        t_title.setStyleSheet(LABEL_STYLE)
        tele_vbox.addWidget(t_title)

        t_sub = QLabel('i j k l ,  /  방향키')
        t_sub.setFont(QFont('Segoe UI', 9))
        t_sub.setStyleSheet('color:#9ca3af; border:none;')
        tele_vbox.addWidget(t_sub)

        # D-pad
        grid = [['', '▲', ''], ['◀', '■', '▶'], ['', '▼', '']]
        acts = [[None, (1,0), None], [(0,1), (0,0), (0,-1)], [None, (-1,0), None]]
        dpad_w = QWidget()
        dpad_l = QVBoxLayout(dpad_w)
        dpad_l.setSpacing(4)
        dpad_l.setContentsMargins(0, 0, 0, 0)
        for r_i, row in enumerate(grid):
            row_h = QHBoxLayout()
            row_h.setSpacing(4)
            for c_i, sym in enumerate(row):
                btn = QPushButton(sym)
                btn.setFixedSize(42, 42)
                btn.setFont(QFont('Segoe UI', 14))
                if sym == '':
                    btn.setEnabled(False)
                    btn.setStyleSheet('background:transparent; border:none;')
                else:
                    btn.setStyleSheet(
                        'background:#f3f4f6; border:1px solid #d1d5db;'
                        'border-radius:7px; color:#374151;'
                    )
                    act = acts[r_i][c_i]
                    if act:
                        btn.pressed.connect(
                            lambda lin=act[0], ang=act[1]: self._send(lin, ang))
                        btn.released.connect(lambda: self._send(0, 0))
                row_h.addWidget(btn)
            dpad_l.addLayout(row_h)
        tele_vbox.addWidget(dpad_w, alignment=Qt.AlignHCenter)

        speed_row = QHBoxLayout()
        sp_lbl = QLabel('속도')
        sp_lbl.setFont(QFont('Segoe UI', 10))
        sp_lbl.setStyleSheet('color:#6b7280; border:none;')
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setRange(1, 10)
        self._slider.setValue(3)
        self._slider.valueChanged.connect(
            lambda v: setattr(self, '_speed_scale', v / 10.0))
        self._sp_val = QLabel('0.3 m/s')
        self._sp_val.setFont(QFont('Segoe UI', 10))
        self._sp_val.setStyleSheet('color:#374151; border:none;')
        self._slider.valueChanged.connect(
            lambda v: self._sp_val.setText(f'{v/10:.1f} m/s'))
        speed_row.addWidget(sp_lbl)
        speed_row.addWidget(self._slider, 1)
        speed_row.addWidget(self._sp_val)
        tele_vbox.addLayout(speed_row)

        # 현재 위치 표시
        self._pose_disp = QLabel('x: --  y: --  yaw: --°')
        self._pose_disp.setFont(QFont('Consolas', 9))
        self._pose_disp.setStyleSheet('color:#6b7280; border:none;')
        tele_vbox.addWidget(self._pose_disp)

        tele_vbox.addStretch()
        main.addWidget(teleop, 1)

        # ── 하단 버튼 ──
        btn_bar = QHBoxLayout()

        del_btn = QPushButton('🗑 삭제')
        del_btn.setStyleSheet(
            'background:#fef2f2; color:#dc2626; border:1px solid #fecaca;'
            'border-radius:6px; padding:7px 16px;'
        )
        del_btn.setVisible(bool(key))
        del_btn.clicked.connect(self._delete)
        btn_bar.addWidget(del_btn)

        btn_bar.addStretch()

        cancel_btn = QPushButton('취소')
        cancel_btn.setStyleSheet(
            'background:#f1f5f9; color:#374151; border:1px solid #d1d5db;'
            'border-radius:6px; padding:7px 20px;'
        )
        cancel_btn.clicked.connect(self.reject)
        btn_bar.addWidget(cancel_btn)

        save_btn = QPushButton('저장')
        save_btn.setStyleSheet(
            'background:#1e40af; color:#fff; border:none;'
            'border-radius:6px; padding:7px 20px;'
        )
        save_btn.clicked.connect(self._save)
        btn_bar.addWidget(save_btn)

        outer = QVBoxLayout()
        outer.addLayout(main)
        outer.addLayout(btn_bar)
        self.setLayout(outer)

        # 포즈 실시간 갱신
        self._pose_timer = QTimer(self)
        self._pose_timer.timeout.connect(self._refresh_pose_disp)
        self._pose_timer.start(200)

    # ── 동작 ──────────────────────────────────────────────────────────

    def _send(self, lin: int, ang: int) -> None:
        self.ros.publish_cmd_vel(
            self.robot,
            lin * self.LINEAR_SPEED  * self._speed_scale,
            ang * self.ANGULAR_SPEED * self._speed_scale,
        )

    def _refresh_pose_disp(self) -> None:
        pose = self.ros.latest_pose.get(self.robot)
        if pose:
            x, y, yaw = self.ros.pose_to_xyyaw(pose)
            self._pose_disp.setText(
                f'x: {x:.3f}  y: {y:.3f}  yaw: {math.degrees(yaw):.1f}°'
            )

    def _apply_pose(self) -> None:
        pose = self.ros.latest_pose.get(self.robot)
        if pose is None:
            return
        x, y, yaw = self.ros.pose_to_xyyaw(pose)
        self._x_spin.setValue(x)
        self._y_spin.setValue(y)
        self._yaw_spin.setValue(yaw)

    def _save(self) -> None:
        key   = self._key_field.text().strip()
        label = self._label_field.text().strip()
        if not key or not label:
            QMessageBox.warning(self, '입력 오류', 'key와 이름은 필수입니다.')
            return

        action = 'update' if self._orig_key else 'add'
        result = self.ros.call_waypoint_crud(
            action,
            key=key, label=label,
            x=self._x_spin.value(),
            y=self._y_spin.value(),
            yaw=self._yaw_spin.value(),
            robot=self.robot,
        )
        if result['success']:
            self.accept()
        else:
            QMessageBox.critical(self, '저장 실패', result['message'])

    def _delete(self) -> None:
        reply = QMessageBox.question(
            self, '삭제 확인', f'"{self._orig_key}" 를 삭제하겠습니까?',
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        result = self.ros.call_waypoint_crud(
            'delete', key=self._orig_key, robot=self.robot)
        if result['success']:
            self.done(2)  # 2 = deleted
        else:
            QMessageBox.critical(self, '삭제 실패', result['message'])

    # ── 키보드 텔레옵 ─────────────────────────────────────────────────

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


class SettingsView(QWidget):
    def __init__(self, ros_node):
        super().__init__()
        self.ros = ros_node
        self._build_ui()

    def _build_ui(self) -> None:
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(10)

        # ── 연결 상태 카드 ──
        conn_card = QFrame()
        conn_card.setStyleSheet(CARD_STYLE)
        conn_vbox = QVBoxLayout(conn_card)
        conn_vbox.setContentsMargins(14, 12, 14, 12)
        conn_vbox.setSpacing(6)

        conn_title = QLabel('📡 연결 상태')
        conn_title.setFont(QFont('Segoe UI', 12, QFont.Bold))
        conn_title.setStyleSheet(LABEL_STYLE)
        conn_vbox.addWidget(conn_title)

        self._conn_limo1 = QLabel('LIMO 1  ● 대기')
        self._conn_limo2 = QLabel('LIMO 2  ● 대기')
        for lbl in (self._conn_limo1, self._conn_limo2):
            lbl.setFont(QFont('Segoe UI', 11))
            lbl.setStyleSheet('color:#9ca3af; border:none;')
            conn_vbox.addWidget(lbl)

        vbox.addWidget(conn_card)

        # ── PIN 변경 카드 ──
        pin_card = QFrame()
        pin_card.setStyleSheet(CARD_STYLE)
        pin_vbox = QVBoxLayout(pin_card)
        pin_vbox.setContentsMargins(14, 12, 14, 12)
        pin_vbox.setSpacing(8)

        pin_title = QLabel('🔑 PIN 변경')
        pin_title.setFont(QFont('Segoe UI', 12, QFont.Bold))
        pin_title.setStyleSheet(LABEL_STYLE)
        pin_vbox.addWidget(pin_title)

        pin_row = QHBoxLayout()
        self._new_pin = QLineEdit()
        self._new_pin.setPlaceholderText('새 PIN (4자리 숫자)')
        self._new_pin.setMaxLength(4)
        self._new_pin.setEchoMode(QLineEdit.Password)
        self._new_pin.setStyleSheet(
            'border:1px solid #d1d5db; border-radius:6px; padding:6px; width:160px;'
        )
        pin_row.addWidget(self._new_pin)
        pin_save_btn = QPushButton('변경')
        pin_save_btn.setStyleSheet(
            'background:#1e40af; color:#fff; border:none; border-radius:6px; padding:6px 16px;'
        )
        pin_save_btn.clicked.connect(self._change_pin)
        pin_row.addWidget(pin_save_btn)
        pin_row.addStretch()
        pin_vbox.addLayout(pin_row)

        self._pin_msg = QLabel('')
        self._pin_msg.setFont(QFont('Segoe UI', 10))
        self._pin_msg.setStyleSheet('color:#16a34a; border:none;')
        pin_vbox.addWidget(self._pin_msg)

        vbox.addWidget(pin_card)

        # ── Waypoint 카드 ──
        wp_card = QFrame()
        wp_card.setStyleSheet(CARD_STYLE)
        wp_vbox = QVBoxLayout(wp_card)
        wp_vbox.setContentsMargins(14, 12, 14, 12)
        wp_vbox.setSpacing(8)

        wp_header = QHBoxLayout()
        wp_title = QLabel('📍 Waypoint 목록')
        wp_title.setFont(QFont('Segoe UI', 12, QFont.Bold))
        wp_title.setStyleSheet(LABEL_STYLE)
        wp_header.addWidget(wp_title)
        wp_header.addStretch()

        # 로봇 선택 (어느 로봇의 waypoint_crud 서비스를 호출할지)
        self._robot_combo = _small_combo(['LIMO 1 (서버1)', 'LIMO 2 (서버2)'])
        wp_header.addWidget(QLabel('대상:'))
        wp_header.addWidget(self._robot_combo)

        add_btn = QPushButton('+ 추가')
        add_btn.setStyleSheet(
            'background:#1e40af; color:#fff; border:none; border-radius:6px; padding:5px 14px;'
        )
        add_btn.clicked.connect(self._open_add)
        wp_header.addWidget(add_btn)

        wp_vbox.addLayout(wp_header)

        self._wp_table = QTableWidget()
        self._wp_table.setColumnCount(len(WP_COLUMNS))
        self._wp_table.setHorizontalHeaderLabels(WP_COLUMNS)
        self._wp_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._wp_table.horizontalHeader().setFont(QFont('Segoe UI', 10, QFont.Bold))
        self._wp_table.setFont(QFont('Segoe UI', 10))
        self._wp_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._wp_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._wp_table.verticalHeader().setVisible(False)
        self._wp_table.setStyleSheet(
            'QTableWidget { border:1px solid #e5e7eb; border-radius:8px; background:#fff; }'
            'QHeaderView::section { background:#f8fafc; border:none;'
            '  border-bottom:1px solid #e5e7eb; padding:6px; }'
        )
        wp_vbox.addWidget(self._wp_table, 1)

        edit_row = QHBoxLayout()
        edit_row.addStretch()
        self._edit_btn = QPushButton('편집')
        self._edit_btn.setStyleSheet(
            'background:#f1f5f9; border:1px solid #d1d5db; border-radius:6px;'
            'padding:6px 20px; color:#374151;'
        )
        self._edit_btn.clicked.connect(self._open_edit)
        edit_row.addWidget(self._edit_btn)
        wp_vbox.addLayout(edit_row)

        vbox.addWidget(wp_card, 1)

        # 연결 상태 타이머
        conn_timer = QTimer(self)
        conn_timer.timeout.connect(self._refresh_conn)
        conn_timer.start(2000)

        QTimer.singleShot(800, self._refresh_waypoints)

    # ── 연결 상태 ────────────────────────────────────────────────────

    def _refresh_conn(self) -> None:
        for robot, lbl in (('limo1', self._conn_limo1), ('limo2', self._conn_limo2)):
            name = 'LIMO 1' if robot == 'limo1' else 'LIMO 2'
            conn = self.ros.is_connected(robot)
            if conn:
                lbl.setText(f'{name}  ● 연결됨')
                lbl.setStyleSheet('color:#16a34a; border:none;')
            else:
                lbl.setText(f'{name}  ● 연결 끊김')
                lbl.setStyleSheet('color:#ef4444; border:none;')

    # ── PIN 변경 ──────────────────────────────────────────────────────

    def _change_pin(self) -> None:
        new_pin = self._new_pin.text().strip()
        if len(new_pin) != 4 or not new_pin.isdigit():
            self._pin_msg.setText('4자리 숫자를 입력해주세요.')
            self._pin_msg.setStyleSheet('color:#ef4444; border:none;')
            return
        # MainWindow의 로그인 뷰 PIN 업데이트
        top = self.window()
        if hasattr(top, '_login_view'):
            top._login_view._correct_pin = new_pin
        self._pin_msg.setText('PIN이 변경되었습니다.')
        self._pin_msg.setStyleSheet('color:#16a34a; border:none;')
        self._new_pin.clear()
        QTimer.singleShot(3000, lambda: self._pin_msg.setText(''))

    # ── Waypoint 관리 ────────────────────────────────────────────────

    def _current_robot(self) -> str:
        return 'limo1' if self._robot_combo.currentIndex() == 0 else 'limo2'

    def _refresh_waypoints(self) -> None:
        result = self.ros.call_waypoint_crud('list', robot=self._current_robot())
        if not result['success']:
            return
        wps = json.loads(result['waypoints_json'])
        self._wp_table.setRowCount(len(wps))
        for row, (key, wp) in enumerate(wps.items()):
            for col, val in enumerate([
                key, wp.get('label', ''),
                f"{wp.get('x', 0):.4f}",
                f"{wp.get('y', 0):.4f}",
                f"{wp.get('yaw', 0):.4f}",
            ]):
                self._wp_table.setItem(row, col, QTableWidgetItem(str(val)))

    def _open_add(self) -> None:
        dlg = WaypointEditDialog(self, self.ros, self._current_robot())
        if dlg.exec_() == QDialog.Accepted:
            self._refresh_waypoints()

    def _open_edit(self) -> None:
        row = self._wp_table.currentRow()
        if row < 0:
            QMessageBox.information(self, '선택 필요', '편집할 waypoint를 선택해주세요.')
            return
        key   = self._wp_table.item(row, 0).text()
        label = self._wp_table.item(row, 1).text()
        x     = float(self._wp_table.item(row, 2).text())
        y     = float(self._wp_table.item(row, 3).text())
        yaw   = float(self._wp_table.item(row, 4).text())

        dlg = WaypointEditDialog(
            self, self.ros, self._current_robot(),
            key=key, label=label, x=x, y=y, yaw=yaw,
        )
        result = dlg.exec_()
        if result in (QDialog.Accepted, 2):  # 저장 or 삭제
            self._refresh_waypoints()


def _small_combo(items: list[str]) -> QComboBox:
    cb = QComboBox()
    cb.addItems(items)
    cb.setStyleSheet('border:1px solid #d1d5db; border-radius:6px; padding:3px 8px;')
    return cb
