# Decision Log

## Pending

---

### DEC-010: Domain Bridge 실행 위치 및 설정 구조
- **Context**: 노트북에 ROS 워크스페이스가 없어 `laptop_bridge_launch.py`를 노트북에서 실행 불가. 브릿지를 어디서 어떻게 실행할 것인가.
- **Options**:
  - A) 노트북에 wego_fleet 패키지 설치
  - B) 각 로봇에서 domain_bridge 실행 (push 방식)
- **Decision**: **B — 각 로봇에서 실행**
- **Rationale**:
  - 노트북은 RViz 전용으로 유지. 워크스페이스 설치 불필요.
  - 단일 템플릿 YAML(`domain_bridge_robot.yaml`) + `ROS_DOMAIN_ID` 환경변수로 `from_domain` 자동 결정 → yaml 파일 하나로 모든 로봇 공유.
  - `/map` 전송 여부는 `leader:=true` 인자로 결정 → 리더 로봇 한 대만 전송.
- **구현**:
  - `wego_fleet/config/domain_bridge_robot.yaml`: `ROBOT_DOMAIN` 플레이스홀더 템플릿
  - `wego_fleet/launch/robot_bridge_launch.py`: OpaqueFunction으로 환경변수 읽어 치환, tempfile 전달
- **실행**:
  ```bash
  ros2 launch wego_fleet robot_bridge_launch.py leader:=true   # 리더
  ros2 launch wego_fleet robot_bridge_launch.py                # 서브
  ```
- **Date**: 2026-04-17

---

### DEC-008: 멀티로봇 TF 프레임 ID 분리 방법
- **Context**: 두 로봇의 /tf를 노트북에서 합산할 때 `odom`, `base_link` 등 프레임 이름이 충돌. 각 로봇의 TF 프레임을 어떻게 분리할 것인가.
- **Options**:
  - A) 로봇에서 직접 수정: robot_state_publisher `frame_prefix` + EKF `odom_frame`/`base_link_frame` 변경 → launch 인자로 제어
  - B) 노트북 relay 노드: domain_bridge로 `/tf`를 `/robot1/tf`로 수신 후 노드에서 프레임 이름 변환
- **Decision**: **A — 로봇에서 직접 수정**
- **Rationale**:
  - B는 노트북 relay 노드에 의존성 생김. 노트북 없이 두 로봇만 운용 시 TF 충돌 발생.
  - A는 각 로봇이 처음부터 올바른 프레임 이름을 발행. 어느 domain에서 수신해도 일관성 유지.
  - AMCL/Nav2/EKF/robot_state_publisher 모두 같은 `robot_name` 런치 인자 하나로 통일 관리.
  - 로봇 3대 확장 시 launch 인자만 바꾸면 됨 (yaml/코드 수정 불필요).
- **구현**:
  - `teleop_launch.py`: `robot_name` 인자 추가, OpaqueFunction 재구성
    - `robot_state_publisher`: `frame_prefix: robot_name + "/"` 추가
    - EKF: `wego_ws` 수정 불가 → `ulsan_ws/src/wego/config/limo_ekf_robot.yaml` 신규, ROBOT_NAME 치환
  - `navigation_diff_launch.py`: 기존 robot_name 인자 + ROBOT_NAME 치환 유지
- **TF 체인**:
  ```
  map (공유 전역 프레임, 불변)
  ├── robot1/odom → robot1/base_link → robot1/base_scan ...
  └── robot2/odom → robot2/base_link → robot2/base_scan ...
  ```
- **Date**: 2026-04-17

---

### DEC-009: Domain Bridge 실행 위치 및 구성
- **Context**: domain_bridge를 어디서 실행하고 어떻게 구성할 것인가.
- **Options**:
  - A) 각 로봇에서 실행: 자신의 토픽을 다른 domain으로 직접 push
  - B) 노트북에서 실행: 노트북이 두 domain에서 pull
- **Decision**: **B — 노트북에서 실행**
- **Rationale**:
  - 로봇은 주행/센서 처리 부하가 높음. bridge 프로세스 분리로 로봇 자원 절약.
  - 노트북에서 두 bridge 프로세스를 한 런치 파일로 관리 → 운용 편의성.
  - domain_bridge는 어느 기기에서 실행해도 동작.
- **구현**:
  - `wego_fleet/config/domain_bridge_robot1.yaml`: domain6→5(/tf,/map), domain6→7(/amcl_pose)
  - `wego_fleet/config/domain_bridge_robot2.yaml`: domain7→5(/tf), domain7→6(/amcl_pose)
  - `wego_fleet/launch/laptop_bridge_launch.py`: bridge x2 + RViz 실행
- **Date**: 2026-04-17

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
