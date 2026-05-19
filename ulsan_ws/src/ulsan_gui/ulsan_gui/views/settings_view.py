import json
import math

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog,
    QDoubleSpinBox, QSlider, QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from ulsan_gui.views.robot_view import TELEOP_KEYS


class _FastApiChecker(QThread):
    done = pyqtSignal(bool)

    def run(self) -> None:
        try:
            import requests
            r = requests.get('http://localhost:8000/logs', timeout=0.5)
            self.done.emit(r.ok)
        except Exception:
            self.done.emit(False)

CARD_STYLE  = 'background:#fff; border-radius:10px; border:1px solid #e5e7eb;'
LABEL_STYLE = 'color:#111827; border:none;'

WP_COLUMNS = ['key', '이름(label)', 'x', 'y', 'yaw (rad)']

CONN_ITEMS = [
    ('LIMO 1',           'limo1_conn',  ''),
    ('LIMO 2',           'limo2_conn',  ''),
    ('FastAPI 서버',      'api_conn',    ''),
    ('wego_bridge (L1)', 'bridge_l1',   'Domain 6 ↔ 5'),
    ('wego_bridge (L2)', 'bridge_l2',   'Domain 7 ↔ 5'),
    ('wego_dispatcher',  'dispatcher',  'Domain 5'),
    ('wego_traffic',     'traffic',     'Domain 5'),
]


class SettingsView(QWidget):
    def __init__(self, ros_node):
        super().__init__()
        self.ros = ros_node
        self._build_ui()

    def _build_ui(self) -> None:
        # 2열 레이아웃: 좌(연결상태) | 우(PIN변경 + Waypoint)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        outer.addWidget(self._build_conn_card(), 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(10)
        right_col.addWidget(self._build_pin_card())
        right_col.addWidget(self._build_wp_card(), 1)

        right_widget = QWidget()
        right_widget.setLayout(right_col)
        outer.addWidget(right_widget, 1)

        # 연결 상태 타이머
        conn_timer = QTimer(self)
        conn_timer.timeout.connect(self._refresh_conn)
        conn_timer.start(2000)
        self._refresh_conn()

        QTimer.singleShot(800, self._refresh_waypoints)

    # ── 연결 상태 카드 ───────────────────────────────────────────────

    def _build_conn_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(16, 14, 16, 14)
        vbox.setSpacing(6)

        title = QLabel('🔌 연결 상태')
        title.setFont(QFont('Segoe UI', 13, QFont.Bold))
        title.setStyleSheet(LABEL_STYLE)
        vbox.addWidget(title)

        self._conn_vals: dict[str, QLabel] = {}
        for label, key, val_text in CONN_ITEMS:
            item = QFrame()
            item.setStyleSheet(
                'background:#f8fafc; border-radius:8px; border:1px solid #f1f5f9;'
            )
            rh = QHBoxLayout(item)
            rh.setContentsMargins(12, 8, 12, 8)

            lbl = QLabel(label)
            lbl.setFont(QFont('Segoe UI', 11))
            lbl.setStyleSheet('color:#6b7280; border:none; background:transparent;')
            rh.addWidget(lbl)
            rh.addStretch()

            if val_text:
                val = QLabel(val_text)
                val.setFont(QFont('Consolas', 11))
                val.setStyleSheet('color:#374151; border:none; background:transparent;')
                rh.addWidget(val)
                rh.addSpacing(8)

            status_lbl = QLabel('● 확인 중')
            status_lbl.setFont(QFont('Segoe UI', 11, QFont.Bold))
            status_lbl.setStyleSheet('color:#9ca3af; border:none; background:transparent;')
            rh.addWidget(status_lbl)

            self._conn_vals[key] = status_lbl

            vbox.addWidget(item)

        vbox.addStretch()
        return card

    # ── PIN 변경 카드 ───────────────────────────────────────────────

    def _build_pin_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(16, 14, 16, 14)
        vbox.setSpacing(10)

        title = QLabel('🔑 PIN 변경')
        title.setFont(QFont('Segoe UI', 13, QFont.Bold))
        title.setStyleSheet(LABEL_STYLE)
        vbox.addWidget(title)

        def _pin_field(label: str) -> QLineEdit:
            lbl = QLabel(label)
            lbl.setFont(QFont('Segoe UI', 10, QFont.Bold))
            lbl.setStyleSheet('color:#6b7280; border:none;')
            vbox.addWidget(lbl)
            field = QLineEdit()
            field.setMaxLength(4)
            field.setEchoMode(QLineEdit.Password)
            field.setPlaceholderText('••••')
            field.setFont(QFont('Segoe UI', 14))
            field.setFixedHeight(40)
            field.setStyleSheet(
                'border:1px solid #d1d5db; border-radius:6px; padding:0 10px;'
                'letter-spacing:4px;'
            )
            vbox.addWidget(field)
            return field

        self._cur_pin  = _pin_field('현재 PIN')
        self._new_pin  = _pin_field('새 PIN')
        self._conf_pin = _pin_field('새 PIN 확인')

        save_btn = QPushButton('PIN 변경 저장')
        save_btn.setFixedHeight(40)
        save_btn.setFont(QFont('Segoe UI', 12, QFont.Bold))
        save_btn.setStyleSheet(
            'background:#1e40af; color:#fff; border:none; border-radius:6px;'
        )
        save_btn.clicked.connect(self._change_pin)
        vbox.addWidget(save_btn)

        self._pin_msg = QLabel('')
        self._pin_msg.setFont(QFont('Segoe UI', 10))
        self._pin_msg.setStyleSheet('color:#16a34a; border:none;')
        vbox.addWidget(self._pin_msg)

        return card

    # ── Waypoint 카드 ────────────────────────────────────────────────

    def _build_wp_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel('📍 Waypoint 목록')
        title.setFont(QFont('Segoe UI', 13, QFont.Bold))
        title.setStyleSheet(LABEL_STYLE)
        header.addWidget(title)
        header.addStretch()

        self._robot_combo = _small_combo(['LIMO 1 (서버1)', 'LIMO 2 (서버2)'])
        header.addWidget(QLabel('대상:'))
        header.addWidget(self._robot_combo)

        add_btn = QPushButton('+ 추가')
        add_btn.setFont(QFont('Segoe UI', 11))
        add_btn.setStyleSheet(
            'background:#1e40af; color:#fff; border:none; border-radius:6px; padding:5px 14px;'
        )
        add_btn.clicked.connect(self._open_add)
        header.addWidget(add_btn)
        vbox.addLayout(header)

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
        vbox.addWidget(self._wp_table, 1)

        edit_row = QHBoxLayout()
        edit_row.addStretch()
        self._edit_btn = QPushButton('편집')
        self._edit_btn.setFont(QFont('Segoe UI', 11))
        self._edit_btn.setStyleSheet(
            'background:#f1f5f9; border:1px solid #d1d5db; border-radius:6px;'
            'padding:6px 20px; color:#374151;'
        )
        self._edit_btn.clicked.connect(self._open_edit)
        edit_row.addWidget(self._edit_btn)
        vbox.addLayout(edit_row)

        return card

    # ── 연결 상태 갱신 ───────────────────────────────────────────────

    def _refresh_conn(self) -> None:
        # LIMO 연결 (토픽 수신 여부)
        for robot, key in (('limo1', 'limo1_conn'), ('limo2', 'limo2_conn')):
            lbl = self._conn_vals.get(key)
            if lbl is None:
                continue
            conn = self.ros.is_connected(robot)
            lbl.setText('● 연결됨' if conn else '● 연결 끊김')
            lbl.setStyleSheet(
                f'color:{"#059669" if conn else "#ef4444"};'
                'border:none; background:transparent;'
            )

        # wego_bridge: 해당 로봇 토픽 수신 여부로 추론
        for robot, key in (('limo1', 'bridge_l1'), ('limo2', 'bridge_l2')):
            lbl = self._conn_vals.get(key)
            if lbl is None:
                continue
            conn = self.ros.is_connected(robot)
            lbl.setText('● 연결됨' if conn else '● 끊김')
            lbl.setStyleSheet(
                f'color:{"#059669" if conn else "#ef4444"};'
                'border:none; background:transparent;'
            )

        # FastAPI ping (별도 스레드)
        if not hasattr(self, '_api_checker') or not self._api_checker.isRunning():
            self._api_checker = _FastApiChecker()
            self._api_checker.done.connect(self._on_api_result)
            self._api_checker.start()

        # ROS 노드 이름으로 dispatcher / traffic 확인
        try:
            node_names = self.ros.get_node_names()
            for key, node_name in (('dispatcher', 'wego_dispatcher'), ('traffic', 'wego_traffic')):
                lbl = self._conn_vals.get(key)
                if lbl is None:
                    continue
                if node_name in node_names:
                    lbl.setText('● 실행 중')
                    lbl.setStyleSheet('color:#059669; border:none; background:transparent;')
                else:
                    lbl.setText('● 미실행')
                    lbl.setStyleSheet('color:#ef4444; border:none; background:transparent;')
        except Exception:
            pass

    def _on_api_result(self, ok: bool) -> None:
        lbl = self._conn_vals.get('api_conn')
        if lbl:
            lbl.setText('● 응답 정상' if ok else '● 미연결')
            lbl.setStyleSheet(
                f'color:{"#059669" if ok else "#ef4444"};'
                'border:none; background:transparent;'
            )

    # ── PIN 변경 ─────────────────────────────────────────────────────

    def _change_pin(self) -> None:
        cur  = self._cur_pin.text().strip()
        new  = self._new_pin.text().strip()
        conf = self._conf_pin.text().strip()

        top = self.window()
        correct = getattr(getattr(top, '_login_view', None), '_correct_pin', None)

        def _err(msg: str) -> None:
            self._pin_msg.setText(msg)
            self._pin_msg.setStyleSheet('color:#ef4444; border:none;')
            QTimer.singleShot(3000, lambda: self._pin_msg.setText(''))

        if correct and cur != correct:
            _err('현재 PIN이 올바르지 않습니다.')
            return
        if len(new) != 4 or not new.isdigit():
            _err('새 PIN은 4자리 숫자여야 합니다.')
            return
        if new != conf:
            _err('새 PIN 확인이 일치하지 않습니다.')
            return

        if hasattr(top, '_login_view'):
            top._login_view._correct_pin = new
        self._pin_msg.setText('PIN이 변경되었습니다.')
        self._pin_msg.setStyleSheet('color:#16a34a; border:none;')
        self._cur_pin.clear()
        self._new_pin.clear()
        self._conf_pin.clear()
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
        if dlg.exec_() in (QDialog.Accepted, 2):
            self._refresh_waypoints()


# ── Waypoint 편집 다이얼로그 ─────────────────────────────────────────

class WaypointEditDialog(QDialog):
    LINEAR_SPEED  = 0.3
    ANGULAR_SPEED = 0.5

    def __init__(self, parent, ros_node, robot: str,
                 key: str = '', label: str = '',
                 x: float = 0.0, y: float = 0.0, yaw: float = 0.0):
        super().__init__(parent)
        self.ros      = ros_node
        self.robot    = robot
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

        grid = [['', '▲', ''], ['◀', '■', '▶'], ['', '▼', '']]
        acts = [[None,(1,0),None],[(0,1),(0,0),(0,-1)],[None,(-1,0),None]]
        dpad_w = QWidget()
        dpad_l = QVBoxLayout(dpad_w)
        dpad_l.setSpacing(4)
        dpad_l.setContentsMargins(0, 0, 0, 0)
        for r_i, row in enumerate(grid):
            row_h = QHBoxLayout()
            row_h.setSpacing(4)
            for c_i, sym in enumerate(row):
                btn = QPushButton(sym if sym != '■' else '정지')
                btn.setFixedSize(42, 42)
                btn.setFont(QFont('Segoe UI', 14 if sym not in ('■', '') else 10))
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
                        btn.pressed.connect(lambda lin=act[0], ang=act[1]: self._send(lin, ang))
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
        self._slider.valueChanged.connect(lambda v: setattr(self, '_speed_scale', v / 10.0))
        self._sp_val = QLabel('0.3 m/s')
        self._sp_val.setFont(QFont('Segoe UI', 10))
        self._sp_val.setStyleSheet('color:#374151; border:none;')
        self._slider.valueChanged.connect(lambda v: self._sp_val.setText(f'{v/10:.1f} m/s'))
        speed_row.addWidget(sp_lbl)
        speed_row.addWidget(self._slider, 1)
        speed_row.addWidget(self._sp_val)
        tele_vbox.addLayout(speed_row)

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

        self._pose_timer = QTimer(self)
        self._pose_timer.timeout.connect(self._refresh_pose_disp)
        self._pose_timer.start(200)

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
            action, key=key, label=label,
            x=self._x_spin.value(), y=self._y_spin.value(), yaw=self._yaw_spin.value(),
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
        result = self.ros.call_waypoint_crud('delete', key=self._orig_key, robot=self.robot)
        if result['success']:
            self.done(2)
        else:
            QMessageBox.critical(self, '삭제 실패', result['message'])

    def keyPressEvent(self, event) -> None:
        if event.isAutoRepeat():
            return
        act = TELEOP_KEYS.get(event.key())
        if act:
            self._send(act[0], act[1])
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.isAutoRepeat():
            return
        if event.key() in TELEOP_KEYS and event.key() not in (Qt.Key_K, Qt.Key_Space):
            self._send(0, 0)
        else:
            super().keyReleaseEvent(event)


_COMBO_STYLE = (
    'QComboBox { border:1px solid #d1d5db; border-radius:6px; padding:4px 10px;'
    '  background:#fff; color:#111827; min-width:90px; }'
    'QComboBox:hover { border-color:#9ca3af; }'
    'QComboBox::drop-down { border:none; width:20px; }'
    'QComboBox QAbstractItemView {'
    '  background:#fff; color:#111827; border:1px solid #d1d5db;'
    '  selection-background-color:#eff6ff; selection-color:#1e40af; outline:0; }'
)


def _small_combo(items: list[str]) -> QComboBox:
    cb = QComboBox()
    cb.addItems(items)
    cb.setFont(QFont('Segoe UI', 10))
    cb.setStyleSheet(_COMBO_STYLE)
    return cb
