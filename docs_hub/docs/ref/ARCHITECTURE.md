# ARCHITECTURE — AI 기반 학원 안내 로봇

## 시스템 개요

```
[ 학원 입구 ]
  ┌──────────────────────┐       ┌──────────────────────┐
  │     리더 로봇         │       │     서브 로봇          │
  │     (Robot 1)        │       │     (Robot 2)         │
  │   DOMAIN_ID=6        │       │   DOMAIN_ID=7         │
  │  드라이버 + perception│       │  드라이버 + perception │
  │  (aruco, 사람감지)    │       │  (aruco, 사람감지)     │
  └──────────┬───────────┘       └──────────┬────────────┘
             │ /amcl_pose,status,diag       │
             └──────────────┬───────────────┘
                            │ (wego_bridge → domain 5)
                  ┌─────────▼──────────┐
                  │   서버 (domain 5)   │
                  │  wego_traffic       │ ← 거리감지 → /pause·/resume
                  │  wego_dispatcher    │ ← FastAPI 폴링 → 임무 배정
                  │  ulsan_gui (관제)   │ ← 위치/상태 표시
                  └────────────────────┘
  ※ Nav2·wego_behaviour·wego_voice는 서버 domain 6/7에서 로봇별로 실행
```

**통신 흐름 요약:**
- 각 로봇 → domain 5: `/amcl_pose`, `/robot_status`, `/diagnostics` → 관제 GUI(ulsan_gui) 표시 (wego_bridge)
- domain 5 → 각 로봇: `/pause`, `/resume`, `/abort`, `/goal_destination`, `/speak_text` (wego_bridge)
- 충돌 회피: wego_traffic(domain 5)이 두 로봇 거리 감지 → `/pause`·`/resume` → wego_behaviour WAITING (우선순위 기반, DEC-022). ※ FleetObstacleLayer(상대 로봇을 가상 장애물로 costmap 주입) 방식은 **폐기**
- `/map`: **domain bridge 없음**. 각 기기(LIMO 1, LIMO 2, 노트북)가 로컬 map_server로 독립 발행 (DEC-012) → 대용량 토픽이 Wi-Fi 미경유 → cyclone unicast 불필요

**맵 배포 방식 (DEC-012)**:
```
LIMO 1 (SLAM) → map.pgm + map.yaml 생성
       ↓ scp
LIMO 2, 노트북에 파일 복사
       ↓
각 기기: map_server → /map 로컬 발행
         LIMO 1, 2: AMCL이 /map 구독
         노트북: 관제 UI가 /map 구독
```

**설계 근거**: Open-RMF(ROS2 공식 fleet 관제 표준)와 동일한 "pose 공유" 원칙. TF 트리/맵 전체를 fleet 경계 너머로 브릿징하지 않고, 위치 정보(pose)만 선택적으로 전달. 2대 소규모 시스템에서 적절한 복잡도.

**임무 배정 원칙 (DEC-027)**: `wego_coordinator`/on_duty 방식은 폐기. 현재는 `wego_dispatcher`(domain 5)가 FastAPI `missions` PENDING을 폴링해 IDLE 로봇에 배정 — LIMO1 우선, 둘 다 IDLE이면 LIMO1, 둘 다 BUSY면 503 반환.

---

## 하드웨어 구성

| 항목 | 사양 |
|------|------|
| 로봇 플랫폼 | Wego (2대) |
| 온보드 컴퓨터 | NVIDIA Jetson Orin Nano |
| GPU | 내장 GPU (CUDA) — YOLOv8n 사람 감지 가속 (로봇 로컬 추론, DEC-043) |
| LiDAR | YDLidar (ydlidar_ros2_driver) |
| 카메라 | Orbbec Dabai DCW (RGB 640×480 + Depth 640×400) — ArUco 도킹 + YOLO 사람 감지 |
| 스피커 | TTS 출력 (edge-tts + mpg123, HDMI 오디오) |
| 네트워크 | Wi-Fi (동일 AP 연결) |

---

## 소프트웨어 스택

| 계층 | 기술 |
|------|------|
| OS | Ubuntu (Jetson 호환 버전) |
| 미들웨어 | ROS 2 Humble |
| DDS | CycloneDDS — **멀티캐스트 auto-discovery + 도메인 분리(5/6/7)** (cyclone_peers.xml 폐기 2026-05-25) |
| SLAM | Cartographer (wego 패키지 내장) |
| 경로 계획 | Nav2 (커스텀 BT XML — DEC-039/041) |
| 위치 추정 | AMCL (Nav2 내장) + ArUco 홈 도킹 PBVS 보정 (wego_aruco) |
| 행동 트리 | 미션: Yasmin FSM (wego_behaviour) / 주행: Nav2 BT + 커스텀 C++ 플러그인(ulsan_bt_plugins) |
| 음성 | **TTS 전용** — edge-tts + mpg123 (DEC-024). ※ VAD/wakeword/STT/NLU 파이프라인은 예약 시스템 도입으로 전부 폐기 |
| 목적지 결정 | 예약 DB 조회 (FastAPI + MySQL) — NLU 미사용 (DEC-023/024) |
| 객체 인식 | YOLOv8n (사람 감지, ulsan_person_detect) + Depth 거리 게이팅 |
| 백엔드/UI | FastAPI + MySQL (ulsan_reservation), React(방문자/웹 예약), PyQt5(ulsan_gui 관제) |

---

## ROS 2 패키지 구성

```
ulsan_ws/src/
├── wego/                  # 로봇 드라이버 + 런치 (teleop/cartographer/navigation_diff)
├── wego_2d_nav/           # Nav2 스택 + 커스텀 BT XML + maps
├── limo_msgs/             # msg/LimoStatus.msg (도메인 브릿지용 로봇 상태)
├── wego_bridge/           # domain bridge (amcl_pose/status/diagnostics ↔ pause/resume/goal/speak)
├── wego_behaviour/        # Yasmin FSM (IDLE/GUIDING/RETURNING/WAITING/FAILED) + Nav2 연동
├── wego_aruco/            # 홈 도킹 PBVS (aruco_home_dock) — 로봇 실행 (DEC-043)
├── ulsan_person_detect/   # YOLOv8 사람 감지 — 로봇 실행 (DEC-043)
├── ulsan_bt_plugins/      # Nav2 BT C++ 플러그인 (PersonClearCondition, DEC-041)
├── wego_voice/            # TTS 전용 (edge-tts + mpg123, DEC-024)
├── wego_traffic/          # 멀티로봇 우선순위 pause/resume (domain 5, DEC-022)
├── wego_dispatcher/       # FastAPI 폴링 → IDLE 로봇 임무 배정 (domain 5, DEC-027)
├── ulsan_gui/             # PyQt 관제 GUI (domain 5)
└── wego_ui/               # RViz 맵 모니터링(보조)
# ※ ulsan_obstacle_layer / wego_msgs / wego_coordinator 는 폐기·삭제됨
# ※ 예약 백엔드·React UI는 ulsan_ws 외부: ~/Ulsan-X/ulsan_ui/ (ulsan_reservation, ulsan-web-ui, ulsan-visitor-ui)
```

---

## 미션 제어 구조 (wego_behaviour)

DEC-014: 최상단은 **Yasmin FSM**, 실행 레이어는 **Nav2 BT** (하이브리드). 임무는 음성 NLU가 아니라 **예약 DB → wego_dispatcher**가 배정 (DEC-023/024/027).

```
방문자 UI(태블릿/브라우저) → FastAPI(ulsan_reservation) missions PENDING
   → wego_dispatcher (domain 5, 0.5s 폴링) → IDLE 로봇에 /goal_destination + /speak_text 발행
        │
        ▼  wego_behaviour FSM (각 로봇 담당, domain 6/7)
        ├── IDLE       — /goal_destination 수신 대기
        ├── GUIDING    — 홈 출발 Spin → navigate_to_pose/Through(목적지) → Nav2 BT 위임
        │                 (실패 시 → FAILED → RETURNING)
        ├── WAITING    — wego_traffic /pause 수신 시 대기 (우선순위 회피, DEC-022)
        ├── FAILED     — TTS 안내 + 10초 대기 → RETURNING (DEC-033)
        └── RETURNING  — navigate(home staging) → wego_aruco /aruco_home_dock PBVS 정밀 정차
                          → IDLE 복귀 → dispatcher가 /complete(or /fail) 처리
```

`wego_behaviour`는 **어디로 갈지** 결정만 담당. 실제 주행은 **Nav2 내부 BT**에 위임 (경로 계획·장애물 회피·복구 포함).

### Nav2 BT 커스텀 노드

| 노드 | 타입 | 상태 | 역할 |
|------|------|------|------|
| `PersonClearCondition` | Condition (C++) | **구현 완료** (DEC-041) | `/person_detected` 구독 → 사람 감지 시 RUNNING 반환 → ReactiveSequence가 FollowPath halt |
| `VoiceTriggerCondition` / `PeerRobotBusyCondition` | Condition | **폐기** | 음성 트리거·on_duty 게이팅은 예약+dispatcher 아키텍처(DEC-027)로 대체되어 불필요 |

---

## 데이터 흐름 요약

```
임무 흐름 (DEC-023/024/027) — 음성 NLU 폐기, 예약 DB 기반
방문자 UI 입력 (예약 조회 / 현장방문 / 강의실 선택)
  → FastAPI(ulsan_reservation): 목적지(상담실/강의실) 확정 + missions PENDING
    → wego_dispatcher (0.5s 폴링): IDLE 로봇 선택 → /goal_destination + /speak_text
      → wego_voice TTS (edge-tts + mpg123) 안내 멘트 출력
      → wego_behaviour FSM (목적지 결정) → Nav2 BT (경로 계획 + 실행)

카메라 입력 (RGB + Depth) — 로봇 로컬 처리 (DEC-043)
  → ulsan_person_detect (YOLOv8n + Depth 0.7m 게이팅) → /person_detected
    → Nav2 BT PersonClearCondition (RUNNING) → FollowPath halt → 주행 정지 (DEC-041)
    → (Phase 4) 방향 추정 → 회전 + 안내 멘트
  → wego_aruco (홈 복귀 시 마커 감지 → PBVS 정밀 정차 → /initialpose AMCL 리셋)
```

---

## 주요 설계 결정 요약

| 결정 | 선택 | 이유 |
|------|------|------|
| DDS | CycloneDDS 멀티캐스트 + 도메인 분리 | `/map` 로컬 발행으로 대용량 토픽 Wi-Fi 미경유 → unicast peers 불필요 (cyclone_peers.xml 폐기 2026-05-25) |
| 멀티로봇 분리 | 도메인 분리(5/6/7) + amcl_pose 공유 (TF prefix 아님) | Open-RMF 동일 원칙. TF 트리 브릿징은 과설계 |
| 지도 공유 | 리더 지도 파일 복사 (DEC-012) | 단일 환경, 실시간 공유 불필요 |
| 충돌 회피 | **우선순위 기반 FSM pause/resume** (wego_traffic → WAITING) | FleetObstacleLayer(가상 장애물 costmap 주입)는 동적 회피 구조적 한계로 **폐기** (DEC-022) |
| perception 배치 | wego_aruco·ulsan_person_detect 로봇 실행 | 카메라 데이터 로컬리티 + 시각 서보 루프 안정성 (DEC-043) |
| 목적지 결정 | 예약 DB 조회 (FastAPI+MySQL) | 음성 NLU 불확실성 제거, 안내 정확도 보장 (DEC-023/024) |
| 음성 | TTS 전용 (edge-tts + mpg123) | 예약 시스템 도입으로 STT/wakeword/NLU 불필요 (DEC-024) |

> 세부 결정 배경(DEC-001~044 전체): [archive/decisions-resolved.md](../archive/decisions-resolved.md) — 미결 결정은 [DECISION-LOG.md](../status/DECISION-LOG.md)
