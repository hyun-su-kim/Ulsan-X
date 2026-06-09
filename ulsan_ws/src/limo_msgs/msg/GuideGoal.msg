# 안내 임무 목표 — 목적지와 출발 안내 멘트를 한 메시지로 묶어 전달.
# goal과 tts를 따로 보내면 둘이 따로 도착하는 레이스가 생겨 'tts 미도착 상태로 출발'이
# 가능하므로, behaviour가 둘을 원자적으로 받도록 묶는다. (wego_dispatcher → wego_behaviour)
string destination   # waypoints.yaml 키 (예: classroom_1)
string tts_text      # 출발 안내 발화 문구 (FastAPI 미션이 제공, 비면 발화 생략)
