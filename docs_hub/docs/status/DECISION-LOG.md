# Decision Log

## Pending

---

### DEC-016: 유리 구간 주행 불안정 해결 방식 + ArUco 마커 운용 전략
- **Context**: 유리 회전 통과 구간에서 로봇이 빙글빙글 돌며 통과 지연. 초기 원인으로 AMCL 파티클 수렴 문제를 의심했으나, RViz 실기기 분석(2026-04-29) 결과 파티클은 정상 수렴 확인. 실제 원인은 **유리 난반사에 의한 유령 장애물(phantom obstacle)**로 재확인.
- **확인된 사실**:
  - LiDAR는 유리를 투과하거나 난반사 → 없는 위치에 장애물이 global costmap에 찍힘
  - 난반사 빔은 raytrace 경로와 달라 자동 소거 불가 → 유령 장애물 지속
  - 유령 장애물이 경로를 막음 → 반복 리플래닝 → 빙글빙글
  - AMCL 파티클은 정상 → ArUco로 유리 구간 AMCL 보정은 불필요
  - 유리문 닫힘 시 경로 생성 불가 → **운용 정책: 유리문은 항상 열린 상태 유지 가정**
- **시도한 해결 방법 및 결과**:
  - `obstacle_max_range` 축소 → phantom이 2m 이내라 효과 없음
  - Keepout Filter 센서 무시 구역 → phantom이 폴리곤 밖에도 찍혀 효과 없음
  - 맵 유리 연장 (GIMP) → 로봇 통과 경로 차단
  - `laser_filters` 각도 필터 → 회전 중 방향 변화로 완벽 해결 불가
  - `observation_persistence` 단축 → 매 스캔 동일 위치 phantom 재생성으로 효과 없음
  - VoxelLayer + Orbbec 카메라 → IR 구조광이 유리 투과, depth 값 없음. 유리 감지 불가로 부적합
- **최종 결정 — Keepout Filter (금지구역) + DenoiseLayer**:
  - Keepout Filter를 **금지구역**으로 사용: 유리 구간 주변 폴리곤 설정 → global planner가 우회 경로 생성 → 로봇이 유리에서 멀어짐 → 난반사 감소
  - DenoiseLayer: Nav2 공식 플러그인. 고립 단일 셀 phantom 필터링. Keepout 보조
  - Nav2 공식 문서 1급 기능. 상용 AMR(iRobot·Locus·Geek+) "가상 벽"과 동일 원리
  - 면접 어필: "LiDAR 물리적 한계를 소프트웨어로 완전 해결할 수 없음을 인지하고, 전역경로 수준에서 유리 근접 자체를 차단하는 산업 표준 방식을 선택했다"
- **ArUco 마커 용도 재정의 (DEC-016 핵심 결정)**:
  - 유리 구간 보정 목적 → **폐기**
  - **목적지(강의실, 상담실 등) 도착 시 누적 오차 보정** 목적으로 재정의
  - 장시간 운영 시 AMCL 누적 드리프트를 각 목적지 마커로 리셋 → 정확한 정차 위치 보장
  - 산업용 AMR 표준 패턴 (물류 로봇의 도킹 마커와 동일 원리)
  - 면접 어필: "장시간 운영 시 발생하는 AMCL 누적 오차를 목적지 ArUco 마커로 보정하여 정확한 정차 위치를 보장하는 구조를 설계했다."
- **마커 사양**: ArUco DICT_4X4_50, 10cm × 10cm, 종이 인쇄, 각 목적지 벽 부착
- **구현 패키지**: `wego_aruco` (신규, ament_python) — 상세 설계는 `docs/ref/ARUCO-LOCALIZER.md`
- **Date**: 2026-04-28 (재확정: 2026-04-29)

---

### DEC-015: 멀티로봇 임무 할당 방식 — 분산 FSM vs 중앙 코디네이터
- **Context**: LIMO 1이 임무 중일 때 새 방문자가 오면 누가 응대하는가. 각 로봇이 상대 상태를 보고 스스로 판단(분산)할지, 노트북 코디네이터가 결정(중앙화)할지 선택 필요.
- **Options**:
  - A) 분산 FSM: 각 로봇이 상대 robot_status 구독 → 스스로 수락/거절 판단
  - B) 중앙 코디네이터 (노트북): 각 로봇 상태 구독 → on_duty 로봇 지정
- **Decision**: **B — 중앙 코디네이터**
- **Rationale**:
  - 분산 방식은 로봇 추가 시 모든 FSM 로직을 수정해야 함 (하드코딩된 peer 관계). 확장성 없음.
  - 중앙 코디네이터는 로봇 수에 무관하게 on_duty 결정 로직이 동일. 로봇 추가 시 status 토픽만 추가.
  - Open-RMF(ROS2 공식 멀티로봇 표준)의 Dispatcher 패턴과 동일한 원칙. 단, Open-RMF는 bidding 방식이고 우리는 2대 고정이므로 코디네이터가 직접 결정하는 단순화 버전.
  - 면접 어필: "Open-RMF의 dispatcher 패턴과 동일한 원칙이며, 2대 규모에서 bidding을 단순화한 트레이드오프를 인지하고 선택했다"고 설명 가능.
- **on_duty 결정 규칙**:
  | LIMO 1 | LIMO 2 | on_duty |
  |--------|--------|---------|
  | IDLE | IDLE | LIMO 1 |
  | BUSY | IDLE | LIMO 2 |
  | IDLE | BUSY | LIMO 1 |
  | BUSY | BUSY | 없음 |
- **on_duty 로봇 역할**: 사람 감지 → "어서오세요" → 음성 대화(STT/NLU) → 목적지 확정 → navigate_to_pose 호출까지 전체 파이프라인 자율 수행
- **토픽 구조**:
  - `/limo_N/robot_status` (로봇 → 코디네이터): IDLE / BUSY / RETURNING
  - `/limo_N/on_duty` (코디네이터 → 로봇): true / false
- **Date**: 2026-04-27

---

### DEC-014: wego_behaviour 구현 방식 — BT vs FSM
- **Context**: 미션 레벨 제어(대기→호출→안내→복귀)를 BehaviorTree.CPP로 구현하려 했으나, 이 레이어에서 BT의 필요성이 불명확함. 동시에 "BT 설계 경험"을 면접에서 어필하려면 어느 레이어의 BT를 구현해야 하는지 검토 필요.
- **Decision**:
  - `wego_behaviour`: **Yasmin FSM** (Python, ament_python)으로 구현 — 미션 모드 전환 (대기 / 안내 중 / 복귀 중)
  - **Nav2 BT 커스터마이징**: 커스텀 BT 조건·액션 노드 C++ 작성 + XML 트리 수정 — 이것이 면접 어필 포인트
- **Rationale**:
  - Nav2 공식 문서 및 업계 표준: BT는 복구 동작·병렬 행동·복잡한 조건 분기에 적합. 상태 5개 이하의 선형 흐름(우리 미션)에는 FSM이 적절.
  - 자율주행 분야 면접에서 "BT 커스터마이징 경험"은 Nav2 내부 BT(커스텀 노드 작성, XML 설계)를 의미함. wego_behaviour를 BT로 짜는 것은 포트폴리오 가치가 낮음.
  - Yasmin: ROS2 전용 경량 Python FSM 라이브러리. SMACH 후계. 상태 전환이 코드로 명확히 표현됨.
  - 하이브리드 구조(고수준 FSM + 실행 레이어 BT)가 실제 서비스 로봇 업계 트렌드.
- **Nav2 BT 커스텀 노드 후보**:
  - `VoiceTriggerCondition`: 웨이크워드 감지 여부 → BT 컨디션 노드
  - `PeerRobotBusyCondition`: 상대 로봇 임무 중 여부 → BT 컨디션 노드
- **Date**: 2026-04-27

---

### DEC-013: wego_fleet 패키지 분리 — wego_bridge (Python) + wego_fleet (C++)
- **Context**: 현재 `wego_fleet`(Python, ament_python)에 domain bridge launch 파일과 FleetObstacleLayer C++ 플러그인을 함께 넣으려 했으나, C++ Nav2 플러그인은 ament_cmake 패키지여야 하므로 같은 패키지에 공존 불가.
- **Decision**: 패키지를 역할과 빌드 시스템 기준으로 분리
  - `wego_bridge` (Python, ament_python): 현재 `wego_fleet` rename. domain bridge launch 파일만 담당.
  - `wego_fleet` (C++, ament_cmake): FleetObstacleLayer Nav2 costmap 플러그인 전용. 신규 작성.
- **Rationale**:
  - Python launch 파일과 C++ 공유 라이브러리는 빌드 시스템(ament_python vs ament_cmake)이 달라 같은 패키지에 공존 불가.
  - 역할도 분리됨: `wego_bridge`는 통신 인프라(domain bridge), `wego_fleet`은 Nav2 플러그인(장애물 회피 로직).
  - 취업용 프로젝트 관점에서 "각 패키지의 책임이 단일하다"는 설명 가능.
- **실행 예정 작업**: `ulsan_ws/src/wego_fleet/` 디렉토리 및 내부 파일 rename → `wego_bridge/`
- **Date**: 2026-04-22

---

### DEC-012: 맵 배포 방식 — domain bridge 스트리밍 vs 파일 사전 배포
- **Context**: 관제 노트북과 각 로봇이 동일한 맵을 사용해야 함. /map 토픽을 domain bridge로 스트리밍할 것인지, 파일로 미리 배포할 것인지 결정 필요.
- **Options**:
  - A) domain bridge로 `/map` 스트리밍: 리더 로봇이 /map을 domain 5로 실시간 전송
  - B) 맵 파일 사전 배포: SLAM으로 생성한 map.pgm + map.yaml을 scp로 배포, 각 기기가 로컬 map_server 실행
- **Decision**: **B — 맵 파일 사전 배포**
- **Rationale**:
  - `/map`은 OccupancyGrid 메시지로 수십~수백 KB. Wi-Fi 브릿징 시 TS-001 재현 위험.
  - 학원 환경은 정적(맵 변경 없음). 매 부팅마다 스트리밍할 이유 없음.
  - 각 기기가 자체 map_server 실행 → AMCL, Nav2, 관제 UI 모두 로컬 /map 구독 → 네트워크 의존성 제거.
  - domain bridge 설정 단순화: /map 제거, /amcl_pose만 브릿징.
  - `leader:=true` 구분 불필요 → 모든 로봇 동일한 launch 명령.
- **운용 절차**:
  1. LIMO 1에서 Cartographer SLAM 실행 → `ros2 run nav2_map_server map_saver_cli -f ~/map`
  2. `scp map.pgm map.yaml` → LIMO 2, 노트북으로 배포
  3. 각 기기 부팅 시 map_server 노드가 로컬 파일 읽어 /map 발행
- **Date**: 2026-04-21

---

### DEC-011: 멀티로봇 fleet 통신 방식 — TF 공유 vs amcl_pose 공유
- **Context**: 기존 구현에서 TF frame prefix(robot1/base_link 등)로 두 로봇 TF를 분리하고 `/tf` 를 노트북으로 브릿징했음. 이 방식을 폐기하고 amcl_pose 공유 방식으로 전환.
- **Options**:
  - A) TF frame prefix 방식: robot_state_publisher frame_prefix + EKF odom_frame 치환 → `/tf` 브릿징
  - B) amcl_pose 공유 방식: 각 로봇이 표준 TF 유지, `/amcl_pose`만 브릿징
- **Decision**: **B — amcl_pose 공유**
- **Rationale**:
  - Open-RMF(ROS2 공식 fleet 관제 표준)와 동일한 설계 원칙. fleet 경계에서 전달하는 것은 TF 트리가 아니라 pose(위치).
  - TF는 단일 로봇 내부 센서 좌표 변환 도구. domain 경계를 넘어 TF 트리를 브릿징하는 것은 과설계.
  - `/amcl_pose`(PoseWithCovarianceStamped)는 단일 메시지로 위치를 표현. 가볍고 브릿징 신뢰성 높음.
  - `/tf`는 많은 노드가 퍼블리시하는 복합 스트림 → 브릿징 시 타이밍, 중복, 프레임 충돌 위험.
  - 각 로봇의 TF 트리는 독립적으로 완결. 노트북은 pose만 받아 마커로 시각화.
  - Robot 간 회피: 상대 amcl_pose → FleetObstacleLayer → costmap 가상 장애물. Nav2 플래너 변경 없이 적용 가능.
- **폐기된 구현**:
  - `wego/config/limo_ekf_robot.yaml` (ROBOT_NAME 템플릿)
  - teleop_launch.py의 robot_name + frame_prefix 로직
  - wego_fleet domain_bridge 설정 파일들 (TF 브릿징 버전)
- **새 구현 대상**:
  - `wego_fleet/config/domain_bridge_robot.yaml`: amcl_pose → domain5, amcl_pose → peer domain
  - `wego_fleet/launch/robot_bridge_launch.py`: 환경변수로 ROBOT_DOMAIN/PEER_DOMAIN 자동 결정
  - `wego_fleet/fleet_obstacle_layer/`: C++ costmap plugin (FleetObstacleLayer)
- **Date**: 2026-04-21

---

### DEC-010: Domain Bridge 실행 위치 및 노트북 워크스페이스 구성
- **Context**: domain_bridge를 어디서 실행하고, 노트북에 어떤 워크스페이스가 필요한가.
- **Domain Bridge 실행 위치**:
  - **각 LIMO 로봇에서 실행 (push 방식)**
  - 노트북은 domain 5에서 amcl_pose를 수동으로 수신만 함. 브릿지 프로세스 불필요.
  - 단일 템플릿 YAML + `ROS_DOMAIN_ID` 환경변수 → 로봇 1, 2 동일한 launch 명령
- **노트북 워크스페이스 구성**:
  - `wego_fleet` 패키지 불필요: domain_bridge와 FleetObstacleLayer 모두 LIMO에서만 실행
  - `map_server`: `nav2_map_server` apt 패키지만 설치하면 실행 가능. 워크스페이스 불필요.
  - Qt 관제 GUI: `wego_ui` 패키지 신규 작성 → 노트북 워크스페이스에만 존재
  ```
  laptop_ws/src/
  └── wego_ui/    # Qt 관제 GUI (map_server 기동 + 위치 마커 시각화)
  ```
- **구현 (LIMO용)**:
  - `wego_fleet/config/domain_bridge_robot.yaml`: `ROBOT_DOMAIN`, `PEER_DOMAIN`, `ROBOT_NAME` 플레이스홀더 템플릿
  - `wego_fleet/launch/robot_bridge_launch.py`: OpaqueFunction으로 `ROS_DOMAIN_ID` 읽어 치환, tempfile 전달
- **실행**:
  ```bash
  # LIMO 1, LIMO 2 동일한 명령
  ros2 launch wego_fleet robot_bridge_launch.py
  ```
- **Date**: 2026-04-17 (수정: 2026-04-21)

---

### DEC-005: 멀티로봇 분리 방법 — ROS2 namespace vs TF frame 이름 변경
- **Context**: 두 로봇의 TF를 노트북에서 동시에 수신할 때 `base_link`, `odom` 프레임이 충돌. 이를 해결하는 방법 선택 필요.
- **Options**:
  - A) ROS2 namespace 적용 (`/robot1/scan`, `/robot1/odom` 등 모든 토픽에 prefix)
  - B) TF frame ID만 변경 (`robot1/base_link`, `robot1/odom`), 토픽 이름은 유지
- **Decision**: **B — TF frame ID만 변경**
- **Rationale**: 각 로봇이 서로 다른 ROS domain(LIMO1=6, LIMO2=7)에서 동작하므로 `/scan`, `/amcl_pose` 등 토픽 이름이 같아도 도메인이 달라 충돌 없음. 충돌이 발생하는 건 노트북(domain 5)에서 두 로봇의 `/tf`를 머지할 때뿐 → frame ID만 구분하면 충분. namespace 적용 시 `teleop_launch.py`의 모든 드라이버(limo_base, ydlidar, EKF)까지 수정해야 해서 변경 범위가 과대함.
- **Date**: 2026-04-16

---

### DEC-006: Nav2 파라미터 다중 로봇 관리 방법
- **Context**: AMCL, costmap 등 Nav2 파라미터에서 TF frame ID(`base_link`, `odom`)를 로봇별로 다르게 설정해야 함. yaml을 어떻게 관리할 것인가.
- **Options**:
  - A) 로봇별 yaml 2벌 (`diff_navigation_params_robot1.yaml`, `_robot2.yaml`)
  - B) `RewrittenYaml` (Nav2 제공) — 키 이름으로 치환
  - C) Template yaml + Python `str.replace()` — 값 안의 문자열로 치환
- **Decision**: **C — Template yaml + Python str.replace()**
- **Rationale**:
  - A: 로봇 추가 시 파일도 늘어남. 수정 시 두 파일 모두 고쳐야 해 관리 부담.
  - B: `global_frame` 키가 `global_costmap`(값: `map`)과 `local_costmap`(값: `odom`) 두 곳에 존재. RewrittenYaml은 키 이름 기준으로 전체 치환하므로 `map`까지 덮어써버림.
  - C: yaml 값 안에 `ROBOT_NAME` 문자열 플레이스홀더를 삽입. Python `str.replace('ROBOT_NAME', 'robot1')`은 텍스트 전체에서 해당 문자열만 찾아 바꾸므로, `global_frame: map`은 영향 없고 `global_frame: ROBOT_NAME/odom`만 `robot1/odom`으로 치환됨. 로봇 추가 시 yaml 수정 없이 인자만 바꾸면 됨.
- **구현 위치**:
  - `wego_2d_nav/params/diff_navigation_params.yaml` — ROBOT_NAME 플레이스홀더 적용
  - `wego/launch/navigation_diff_launch.py` — OpaqueFunction 내 Python 치환 로직
- **Date**: 2026-04-16

---

### DEC-007: launch 파일에서 OpaqueFunction + tempfile 사용
- **Context**: `robot_name` 인자를 받아 yaml 내용을 치환한 뒤 Nav2에 넘겨야 함. 어떻게 동적으로 파라미터를 전달할 것인가.
- **Decision**: **OpaqueFunction + tempfile**
- **Rationale**:
  - `LaunchConfiguration`은 지연 평가(lazy evaluation) 객체라 Python f-string/str.replace 등 일반 문자열 연산 불가. `perform(context)`로 실행 시점에 실제 문자열로 변환해야 함.
  - `OpaqueFunction`은 launch 실행 시점에 `context`를 받아 Python 함수를 실행하므로, 이 시점에서 `LaunchConfiguration.perform(context)`로 실제 값 추출 가능.
  - Nav2는 파라미터를 파일 경로(`ParameterFile`)로 받음. 치환된 내용을 `tempfile`에 저장 후 그 경로를 전달.
- **Date**: 2026-04-16

---

### DEC-001: openWakeWord 커스텀 모델 필요 여부
- **Context**: "헤이 리모"는 기존 openWakeWord에 없는 커스텀 호출어. 사전 학습된 모델이 없으면 직접 학습 데이터 수집 및 파인튜닝 필요.
- **Options**:
  - A) openWakeWord 커스텀 모델 학습 ("헤이 리모" 샘플 수집 → 학습)
  - B) 기존 영어 호출어로 변경 (예: "hey robot") — 사용자 경험 저하
  - C) 호출어 없이 VAD 후 바로 STT — 오작동 가능성 증가
- **Decision**: 미결정
- **Rationale**: 학습 데이터 수집 공수, 인식률 목표치 확인 후 결정
- **Date**: 2026-04-16

---

### DEC-002: Orin Nano GPU 메모리 — YOLO + faster-whisper 동시 가동
- **Context**: Orin Nano의 GPU 메모리는 제한적. YOLO(상시)와 faster-whisper(호출 시)가 동시에 CUDA를 사용할 경우 OOM(Out of Memory) 발생 가능.
- **Options**:
  - A) 시간 분할: 호출어 감지 시 YOLO 일시 정지 → STT 완료 후 YOLO 재개
  - B) YOLO 모델 경량화 (nano 버전 사용) + faster-whisper tiny 모델 조합
  - C) STT는 CPU fallback (속도 저하 감수)
  - D) 실측 후 결정 (실제 메모리 사용량 프로파일링)
- **Decision**: 미결정 → 실측 우선
- **Rationale**: Orin Nano 실제 VRAM 공유 구조 파악 필요. 프로파일링 없이 결정 불가.
- **Date**: 2026-04-16

---

### DEC-003: wego_behaviour BT 프레임워크 선택
- **Context**: ROS 2에서 BehaviorTree.CPP v3 vs v4, 또는 py_trees 사용 가능. Nav2는 BehaviorTree.CPP 기반.
- **Options**:
  - A) BehaviorTree.CPP v4 (Nav2와 동일 프레임워크 — 연동 용이)
  - B) py_trees (Python 기반 — 프로토타이핑 빠름, 성능 낮음)
- **Decision**: BehaviorTree.CPP v4 방향 (Nav2 연동 일관성)
- **Rationale**: Nav2 BT 액션 노드를 그대로 재사용 가능. 최상단 BT도 동일 프레임워크로 통일.
- **Status**: 결정됨, 구현 전 최종 확인 필요
- **Date**: 2026-04-16

---

### DEC-004: Gemini API 폴백 전략 — 응답 지연 허용 한계
- **Context**: Gemini API는 네트워크 왕복 지연 발생. 안내 로봇 맥락에서 사용자가 기다리는 시간의 UX 한계 정의 필요.
- **Options**:
  - A) 타임아웃 3초 → Gemma-2B 폴백
  - B) 타임아웃 5초 → Gemma-2B 폴백
  - C) Gemini API 먼저 비동기 호출, 동시에 Gemma-2B도 실행 → 먼저 온 결과 사용
- **Decision**: 미결정
- **Rationale**: 실제 학원 환경 네트워크 지연 측정 후 결정
- **Date**: 2026-04-16

## Resolved

> 해결된 결정은 [docs/archive/decisions-resolved.md](../archive/decisions-resolved.md)로 이동
