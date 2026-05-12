# AI 기반 학원 안내 로봇 — Claude 진입점

## 프로젝트 한 줄 요약
2대의 LIMO 로봇(Orin Nano)이 학원 입구에서 방문자를 음성으로 맞이하고 목적지까지 안내하는 멀티로봇 시스템.

---

## 세션 시작 루틴 (필수 — 매 세션 반드시 실행)

Claude가 새 세션을 시작할 때 **아래 순서대로** 수행한 뒤 현재 상태를 요약하고 다음 작업을 제안한다.

### Step 1 — 상태 문서 읽기
| 문서 | 경로 |
|------|------|
| 현재 상태 & 체크리스트 | `docs/status/PROJECT-STATUS.md` |
| 미결 결정 | `docs/status/DECISION-LOG.md` |

### Step 2 — 소스코드 분석
아래 파일을 읽고 현재 구현 상태를 파악한다.

```
ulsan_ws/src/
├── wego/
│   ├── launch/cartographer_launch.py      # SLAM 진입점
│   ├── launch/navigation_diff_launch.py   # Nav2 통합 진입점
│   └── config/limo_lds_2d.lua             # Cartographer 설정
├── wego_2d_nav/
│   ├── launch/localization_launch.py      # AMCL 위치추정
│   ├── launch/navigation_only_launch.py   # Nav2 스택
│   ├── maps/map.yaml                      # 저장된 맵 (존재 여부 확인)
│   └── params/diff_navigation_params.yaml # Nav2 파라미터
├── wego_msgs/
│   └── srv/Chalkak.srv                    # 서비스 정의
└── (wego_behaviour / wego_voice — 미생성 시 신규 작업 대상)
```

### Step 3 — 현재 상태 요약 & 다음 작업 제안
분석 결과를 바탕으로 무엇이 됐고, 무엇을 해야 하는지 간략히 정리 후 사용자에게 제안한다.

---

## 소스코드 현황 (2026-05-11 기준)

### 아키텍처 — 기기별 역할 (2026-05-12 확정)

| 기기 | 도메인 | 실행 내용 |
|------|--------|-----------|
| 관제 노트북 | 5 | wego_ui, wego_bridge |
| LIMO 1 | 6 | 드라이버(limo_base, ydlidar, orbbec, EKF) + wego_touch_ui |
| LIMO 2 | 7 | 드라이버(limo_base, ydlidar, orbbec, EKF) + wego_touch_ui |
| 서버 노트북 | 6 | Nav2(AMCL+planner+controller), wego_behaviour, wego_aruco, wego_voice (LIMO 1 담당) |
| 서버 노트북 | 7 | Nav2(AMCL+planner+controller), wego_behaviour, wego_aruco, wego_voice (LIMO 2 담당) |
| 서버 노트북 | 5 | wego_traffic |

```bash
# LIMO 1 (domain 6) — 드라이버 + 터치 UI
export ROS_DOMAIN_ID=6
ros2 launch wego teleop_launch.py
ros2 launch wego_touch_ui touch_ui_launch.py

# LIMO 2 (domain 7) — 드라이버 + 터치 UI
export ROS_DOMAIN_ID=7
ros2 launch wego teleop_launch.py
ros2 launch wego_touch_ui touch_ui_launch.py

# 서버 노트북 — LIMO 1 담당 터미널 (domain 6)
export ROS_DOMAIN_ID=6
ros2 launch wego_2d_nav navigation_launch.py
ros2 launch wego_behaviour behaviour_launch.py

# 서버 노트북 — LIMO 2 담당 터미널 (domain 7)
export ROS_DOMAIN_ID=7
ros2 launch wego_2d_nav navigation_launch.py
ros2 launch wego_behaviour behaviour_launch.py

# 서버 노트북 — wego_traffic 터미널 (domain 5)
export ROS_DOMAIN_ID=5
ros2 launch wego_traffic traffic_launch.py

# 관제 노트북 (domain 5)
export ROS_DOMAIN_ID=5
ros2 launch wego_ui gui_launch.py
ros2 launch wego_bridge bridge_launch.py  # amcl_pose 6,7→5 / pause_resume 5→6,7
```

### 존재하는 패키지
| 패키지 | 핵심 파일 | 상태 |
|--------|-----------|------|
| `wego` | teleop_launch.py, navigation_diff_launch.py | LIMO 드라이버 전용으로 축소 예정 |
| `wego_2d_nav` | localization_launch.py, navigation_only_launch.py, diff_navigation_params.yaml | 중간 노트북에서 실행 |
| `wego_msgs` | srv/Chalkak.srv | 기본 서비스 |
| `wego_bridge` | domain_bridge_robot.yaml, robot_bridge_launch.py | 관제 UI 노트북에서 실행. amcl_pose(5,6→7) + pause/resume(7→5,6) 양방향 |
| `wego_behaviour` | behaviour_node.py, states.py | Yasmin FSM — WAITING 상태 추가 예정 (DEC-022) |
| `wego_aruco` | pose_corrector.py | passive corrector + calibration_mode 구현 완료 |
| `wego_voice` | voice_node.py, tts | NLU 제거 (DEC-024). TTS만 유지 |
| `ulsan_obstacle_layer` | PeerObstacleLayer | **폐기 (DEC-022)**: 우선순위 FSM pause 방식으로 대체 |
| `wego_touch_ui` | — | **신규** (LIMO): 터치 디스플레이 UI. 예약 조회 + 체크인 + /goal_destination 발행 |
| `wego_traffic` | — | **신규** (서버 노트북 domain 7): 두 로봇 거리 감지 → pause/resume 발행 |
| `reservation_web` | — | **신규** (웹 서비스): 상담 예약 CRUD. 평일 09~17시, 1시간 단위, 상담실 4개 자동 배정 |

### 멀티로봇 충돌 회피 (DEC-022, 2026-05-11 확정)
- **PeerObstacleLayer 폐기**: global costmap 기반 동적 회피의 구조적 한계 확인
- **우선순위 기반 FSM pause/resume 채택**: GUIDING > RETURNING, 동순위 시 LIMO 1 우선
- **구현**: wego_traffic 거리 감지 → pause/resume 토픽 → wego_behaviour WAITING 상태

---

## 영역별 참조 (Tier 2)
| 문서 | 경로 | 참조 시점 |
|------|------|----------|
| 전체 구조 | `docs/ref/ARCHITECTURE.md` | 전체 흐름 파악 시 |
| 노드·토픽 구성 | `docs/ref/NODE-TOPOLOGY.md` | ROS 노드/토픽 작업 시 |
| 음성 파이프라인 | `docs/ref/VOICE-PIPELINE.md` | 음성 관련 작업 시 |
| SLAM & Nav2 | `docs/ref/NAVIGATION.md` | 경로 계획, waypoints 작업 시 |
| 통신 설정 | `docs/ref/COMMUNICATION.md` | CycloneDDS, Domain Bridge 작업 시 |
| ArUco 보정 | `docs/ref/ARUCO-LOCALIZER.md` | ArUco 마커 로컬라이제이션 작업 시 |

## 문서 관리 커맨드
- `/doc-update` — 코드 변경 후 관련 문서 갱신
- `/doc-sync` — 문서 누락 여부만 점검 (수정 없음)
- `tools/prune-status.sh --dry-run` — 오래된 done 항목 미리보기

## 코드 위치
```
/home/wego/Ulsan-X/
├── docs_hub/       ← 이 문서 저장소 (현재 위치)
├── ulsan_ws/src/
│   ├── wego/           # 기존: 드라이버, Cartographer
│   ├── wego_2d_nav/    # 기존: Nav2
│   ├── wego_msgs/      # 기존: 공통 메시지
│   ├── wego_bridge/    # Python: domain bridge (amcl_pose 브릿징)
│   ├── ulsan_obstacle_layer/  # C++: 상대 로봇 amcl_pose → global costmap 장애물 주입
│   ├── wego_behaviour/ # 신규: 최상단 Behavior Tree
│   └── wego_voice/     # 신규: 음성 파이프라인
└── cyclone_peers.xml   # CycloneDDS 유니캐스트 설정
```

## 작업 공간 규칙
- `~/wego_ws` — **절대 수정 금지** (로봇 원본 환경)
- `~/Ulsan-X/ulsan_ws` — 실제 개발 공간. 신규 패키지 및 수정 코드는 여기에만.

## 핵심 원칙
- 정본 1곳: 같은 사실은 하나의 문서에만. 나머지는 링크.
- 구현과 문서 충돌 → 구현 우선, 문서를 맞춤.
- 초안이므로 더 나은 대안이 있으면 언제든 제안.

## 소스코드 수정 규칙
- 수정 전: 무엇을 어떻게 바꿀지 설명 후 **확인을 받고 진행**
- 수정 후: 변경된 파일 경로 목록을 반드시 보고
- 적용 범위: `ulsan_ws` 내 코드 파일(.py, .cpp, .yaml, .launch 등) — docs_hub 문서는 확인 없이 수정 가능

## 개발 방법 추천 원칙 (취업용 프로젝트)
- 개발 방법을 물어보면 직접 서칭 후 비교하여 **최선의 방법과 이유**를 결론으로 제시
- 기술/라이브러리/설계 선택 시 항상 **"왜 이걸 선택했는가"** 근거 포함
- 결정은 DECISION-LOG.md에 Rationale까지 기록 → 면접에서 설명 가능한 수준으로 문서화
- "동작하면 됨" 수준이 아닌 **기술적 판단 근거가 있는 구현**을 목표로 함
