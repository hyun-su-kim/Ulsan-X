# GUI 시각 상수 — 단일 정본
#
# 이벤트/미션 로그 유형별 (배경색, 글자색).
# 의미: 파랑=진행, 초록=성공, 빨강=실패, 황갈=대기, 회색=일반.
LOG_TYPE_COLOR: dict[str, tuple[str, str]] = {
    'mission_start':    ('#dbeafe', '#1d4ed8'),
    'mission_complete': ('#d1fae5', '#047857'),
    'mission_fail':     ('#fee2e2', '#b91c1c'),
    'waiting':          ('#fef3c7', '#b45309'),
    'system':           ('#f3f4f6', '#374151'),
}
