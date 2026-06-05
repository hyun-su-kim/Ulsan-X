# Resolved Decisions

> 해결된 결정을 여기에 보관. DECISION-LOG.md에서 이동됨.
> 형식: 원본 DEC-XXX 항목 + **Resolution** 줄 추가.

### DEC-009: Domain Bridge 실행 위치 및 구성 ~~(Superseded by DEC-010)~~
- **Options**:
  - A) 각 로봇에서 실행: 자신의 토픽을 다른 domain으로 직접 push
  - B) 노트북에서 실행: 노트북이 두 domain에서 pull
- **Decision**: B — 노트북에서 실행
- **Superseded by**: DEC-010 (2026-04-17) — 노트북 워크스페이스 구성 재검토 결과, domain bridge를 각 LIMO에서 push 방식으로 실행하는 것으로 전환. 노트북 의존성 제거 및 단일 launch 명령 통일.
- **Date**: 2026-04-17

---

### DEC-008: 멀티로봇 TF 프레임 ID 분리 방법 ~~(Superseded by DEC-011)~~
- **Options**:
  - A) 로봇에서 직접 수정: robot_state_publisher `frame_prefix` + EKF `odom_frame`/`base_link_frame` 변경
  - B) 노트북 relay 노드: domain_bridge로 `/tf`를 `/robot1/tf`로 수신 후 프레임 이름 변환
- **Decision**: A — 로봇에서 직접 수정
- **Superseded by**: DEC-011 (2026-04-21) — TF 브릿징 방식 전체를 폐기하고 amcl_pose 공유 방식으로 전환. 각 로봇은 표준 TF 프레임(`base_link`, `odom`, `map`) 그대로 유지. TF frame prefix 불필요.
- **Date**: 2026-04-17


---

# DECISION-LOG에서 이관 (2026-06-01 정리)

> 아래는 기존 `DECISION-LOG.md`의 확정·폐기 결정 전체(DEC-001~042). 각 항목 헤딩의 `done (날짜)` / `폐기` / `Superseded by` 표기가 resolution 상태를 나타냄. DEC-043(최신)부터 시간 역순.

### DEC-044: FSM 실패 처리 — 모든 주행/도킹 실패를 FAILED로 통합 + 관리자 물리 복구 (done 2026-06-05)
- **Context**: 기존 FSM의 실패 처리가 불완전·위험. ① `RETURNING failed → IDLE`이라 복귀 주행 실패 시 로봇이 맵 한복판에 멈췄는데 상태는 IDLE → dispatcher가 새 임무 배정 + AMCL 리셋 누락 채로 다음 주행. ② `ReturningState`의 PBVS 도킹(`call_home_dock()`) 반환값을 무시 → 도킹 실패가 silent. ③ `GUIDING failed → FAILED → 10초 후 자동 RETURNING` 자가복구를 두었으나, "Nav2 실패 = 주행 능력이 깨짐"인데 그 깨진 능력으로 복귀를 시도하는 모순 + RETURNING도 실패하면 무한루프 위험.
- **실패 지점 3분류 (코드 확인)**:
  - **GUIDING**(목적지 주행 실패) / **RETURNING**(홈·staging 주행 실패): 위치추정 의심, 로봇은 경로 한복판 → 심각도 높음
  - **DOCKING**(PBVS 마커 도킹 실패): Nav2 본주행은 성공해 staging 도착(위치추정 정상) + 홈 코앞 → 심각도 낮지만, 그래도 정밀 파킹·AMCL 리셋이 누락되므로 표면화 필요
- **Options**:
  - A) 출처별 차등 복구(GUIDING은 1회 자동 복귀 시도, DOCKING은 1회 재시도 후 IDLE 등)
  - B) **모든 실패 → FAILED 통합. 자동 재주행 일절 없음. 관리자가 물리적으로 로봇을 home에 배치 후 UI [복구완료] → home 좌표 `/initialpose`(AMCL 리셋) → IDLE**
- **Decision**: **B 채택.**
- **Rationale**:
  - **모순 제거**: Nav2 실패는 "주행 능력이 깨졌다"는 신호. 깨진 그 능력(주행)으로 자가복구를 시도하는 건 논리적 모순 — 복귀도 실패할 공산이 큼. 자동 재주행을 전면 배제해 이 모순과 무한루프(FAILED↔RETURNING)를 원천 차단.
  - **위치추정 신뢰 회복**: 실패는 대개 localization 상실을 동반. 사람이 로봇을 알려진 home 위치에 물리적으로 놓고 그 좌표로 `/initialpose`를 발행하면, 다음 임무를 **깨끗한 AMCL 상태**에서 시작. (PBVS 도킹의 AMCL 리셋과 동일 효과를 사람이 보장.)
  - **단순성·안전성**: 분기 정책(A)은 케이스마다 동작이 갈려 검증 부담↑. 학원 데모 규모에선 "실패=정지+호출"이 가장 예측 가능하고 안전.
  - **AMCL 리셋 주체**: 복구는 도킹을 거치지 않으므로 `aruco_home_dock`(로봇)이 아니라 **`behaviour_node`(데스크탑, AMCL과 동일 도메인)가 직접 home `/initialpose` 발행**. 도킹 성공 경로의 리셋 로직을 그대로 미러링(covariance 0.05).
- **구현**:
  - `states.py`: `FailedState` 재작성 — `failed_from`(GUIDING/RETURNING/DOCKING)별 TTS 3종 발화 → `/recover` 대기 루프(FAILED 1초 재발행) → `publish_initial_pose_home()` → `recovered`. `GuidingState`/`ReturningState` 실패 시 `blackboard['failed_from']` 기록. `ReturningState`가 `call_home_dock()` 반환값을 받아 False면 `failed_from='DOCKING'`로 표면화.
  - `behaviour_node.py`: `/recover`(Empty) 구독 + `_recover_flag`, `/initialpose` 퍼블리셔 + `publish_initial_pose_home()`(home_key 좌표 사용), SM 전이 `RETURNING failed: IDLE→FAILED` / `FAILED: recovered→IDLE`.
  - `wego_bridge/bridge_robot.yaml`: `/ROBOT_NAME/recover`(domain 5→LIMO) 브릿지 추가(abort 패턴 동일).
  - **관제 GUI [복구완료] 버튼은 미구현(FSM GUI 작업 시 진행)** — `/limo{N}/recover` Empty 발행만 하면 됨.
- **면접 어필**: "FSM 실패 처리를 설계할 때 'Nav2 실패=주행 능력 손상'으로 해석. 손상된 능력으로 자가복구를 시도하는 모순과 FAILED↔RETURNING 무한루프를 진단해, 자동 재주행을 배제하고 human-in-the-loop 물리 복구로 단순화. 복구 시 알려진 home 좌표로 AMCL을 강제 리셋해 위치추정 신뢰를 회복하는 게 핵심 — 실패의 근본 원인(localization 상실)을 정조준."
- **Date**: 2026-06-05

---

### DEC-043: perception 노드(wego_aruco, ulsan_person_detect) 로봇 엣지 배치 (done 2026-06-01)
- **Context**: 기존엔 `wego_aruco`와 `ulsan_person_detect`를 데스크탑 domain 6/7에서 실행. 두 노드 모두 로봇(Orin Nano)의 Orbbec 카메라(`/camera/color/image_raw` 등)를 구독하므로, 카메라 원본 이미지가 WiFi를 건너 데스크탑까지 전송되는 구조였음. 이를 로봇에서 직접 실행하는 게 맞는지 검토.
- **데이터 흐름 분석 (코드 확인)**:
  - `person_detect_node`: RGB + Depth 구독 → `/person_detected`(Bool 1바이트) 발행
  - `aruco_home_dock`: RGB + camera_info 구독 → `/cmd_vel`(Twist) + `/initialpose` 발행. **카메라→cmd_vel 닫힌 시각 서보 루프**
  - 셋 다 "큰 입력(이미지) → 작은 출력(결과 메시지)" 구조
- **대역폭 산정**: color 640×480@30 ≈ 220Mbps + depth 640×400@30 ≈ 123Mbps = 로봇당 ~340Mbps. 2대면 ~680Mbps + LiDAR(Nav2용) → 실측 802.11ac 가용 대역(200~400Mbps) 포화. 카메라 스트림이 amcl_pose 등 작은 메시지 지연도 유발(미해결 이슈 "fleet 위치 업데이트 지연"과 직결).
- **Decision**: **`wego_aruco` + `ulsan_person_detect`를 LIMO 도메인(6/7) = 로봇에서 실행.** `ulsan_bt_plugins`(C++ BT 플러그인)는 bt_navigator가 사는 **데스크탑 유지**(이동 불가).
- **Rationale**:
  - **데이터 로컬리티 (edge processing)**: 큰 데이터는 생산되는 곳(카메라=로봇)에서 처리하고 작은 결과만 네트워크로. 로봇이 "원본 이미지를 흘리는 센서"가 아니라 "사람 감지/포즈 결과를 내놓는 스마트 센서"가 됨.
  - **시각 서보 루프 안정성**: aruco 도킹은 `카메라→추론→cmd_vel→로봇`의 닫힌 피드백 루프. 데스크탑 실행 시 매 틱 WiFi를 두 번(이미지 입력+cmd_vel 출력) 건너 가변 지연(지터)이 제어 안정성을 해침. 로컬 실행 시 루프 전체가 로컬 → DEC-038의 ~1cm 정밀 도킹이 안정적.
  - **WiFi 부하 경감**: 카메라 스트림 제거로 fleet 위치 지연(미해결 이슈) 완화.
  - **엣지 적합성**: YOLOv8n은 Orin 같은 엣지가 타깃 모델. faster-whisper 제거(DEC-024) 후 GPU OOM 리스크도 해소.
  - **분리/배치 원칙(산업 표준)**: 같은 카메라 토픽을 구독한다는 이유로 두 노드를 한 런치로 묶지 않음(리소스 기준 그룹핑은 안티패턴). per-package 런치 단위 유지 + 필요 시 상위 bringup에서 조합. 센서 드라이버 bringup(teleop)에 perception을 섞지 않음.
- **구현 영향 (핵심: 노드 코드 0줄 수정)**:
  - 로봇과 데스크탑은 같은 도메인(6/7)이라 노드를 어느 머신에서 실행하든 ROS 그래프 동일. 토픽 전부 절대경로, 네임스페이스 충돌 없음(도메인당 로봇 1대) → **소스 수정 불필요.**
  - person_detect는 노드 1개라 런치 파일 만들지 않고 `ros2 run`으로 실행(오버엔지니어링 회피).
  - **숨은 의존성**: `aruco_home_dock.py`가 `get_package_share_directory('wego_behaviour')`로 `waypoints.yaml`(AMCL 리셋 home 좌표)을 읽음 → 로봇도 `wego_behaviour`를 빌드해야 함. ament_python 패키지의 colcon build는 파일 복사만 하므로 yasmin/nav2_simple_commander 미설치여도 빌드 통과(노드 실행 안 하면 무관). `wego_aruco/package.xml`에 의존성 미선언 상태(향후 hygiene 정리 후보).
  - 로봇 conda env에서 `rclpy`+`cv_bridge`+`ultralytics` 공존 필요 → Python 3.10 + numpy<2(cv_bridge ABI) 체크포인트(DEC-041 동일 제약).
- **실행 절차**: 로봇 — `teleop_launch.py` + `aruco_corrector_launch.py` + `ros2 run ulsan_person_detect person_detect_node`. 데스크탑 6/7에서 aruco 실행 제거.
- **면접 어필**: "카메라 원본(~340Mbps/대)을 WiFi로 흘리던 구조를 데이터 로컬리티 원칙으로 진단해 perception을 엣지로 이동. 특히 aruco 도킹은 닫힌 시각 서보 루프라 WiFi 지터가 제어 안정성을 해친다는 점을 근거로 제시. 같은 도메인 설계 덕분에 노드 코드 0줄 수정으로 배치만 전환 — ROS2 위치 투명성을 활용. '카메라 공유 = 런치 통합'이 아니라 패키지 소유 기준 분리라는 런치 조합 표준도 적용."
- **Date**: 2026-06-01

---

### DEC-042: PBVS 도킹 제어기 A/B 실험 종료 — polar 제거, staged 단독 채택 (done 2026-06-01)
- **Context**: DEC-038에서 극좌표(polar, A)와 단계분리(staged, B) 두 도킹 제어기를 `dock_mode` 파라미터로 전환하며 실기기 A/B 비교를 진행, staged가 우월함을 입증했다. 그러나 코드·런치에 polar가 그대로 남아 있고 런치 기본값이 `polar`로 설정되어 있어, 인자(`dock_mode:=staged`)를 빠뜨리면 기각된 polar로 도킹되는 운영 리스크가 있었다.
- **Decision**: **polar 제어기 제거 + staged 단독 채택.** A/B 실험을 종료하고 `_ctrl_polar`, `dock_mode` 파라미터, polar 게인(`k_rho`/`k_alpha`/`k_beta`)을 코드·런치에서 모두 제거. 이제 `ros2 launch wego_aruco aruco_corrector_launch.py`만으로 항상 staged 동작.
- **선택 이유 (staged)**:
  - 실기기 비교(DEC-038)에서 staged가 lateral 0.8~1.7cm로 안정 정차. polar는 lateral 1.4cm까지 수렴하나 ω가 ±0.3에 상시 포화하며 심한 S자 사행 발생.
  - 근본 원인: 단일 평면 마커의 법선(out-of-plane 회전) 관측성이 낮아 노이즈가 큼. polar는 이 노이즈 심한 법선을 고게인(k_α=2.0)으로 ω에 직접 추종 → 사행. staged는 위치(ρ)는 직진으로, 자세(θ_g)는 마지막 제자리 회전으로 분리해 노이즈 영향을 시간적으로 격리.
  - 운영 안전성: 단일 제어기로 단순화하면 `dock_mode` 인자 누락 시 polar로 도킹되던 사고 경로가 구조적으로 사라짐.
- **변경 파일**: `wego_aruco/wego_aruco/aruco_home_dock.py` (`_ctrl_polar` 삭제, `dock_mode`/`k_rho`/`k_alpha`/`k_beta` 파라미터 제거, 제어 루프 분기 제거, 로그 3곳 정리, docstring 정리), `wego_aruco/launch/aruco_corrector_launch.py` (`dock_mode` 인자 + polar 게인 제거)
- **보존**: A/B 비교 과정 자체는 DEC-038에 기록 유지(면접 어필 포인트). `markers.yaml`/`target_dist`/staged 게인 등 운영 파라미터는 그대로.
- **면접 어필**: "Lyapunov 극좌표 제어와 단계분리 제어를 실기기 A/B로 비교해 노이즈 심한 단일 마커 환경에서 단계분리의 우월성을 입증한 뒤, 실험을 종료하고 채택안만 남겨 운영 리스크(인자 누락 시 기각안 동작)를 제거. 실험 코드를 프로덕션에 방치하지 않고 정리하는 엔지니어링 규율."
- **Date**: 2026-06-01

---

### DEC-041: 1차 데모 마무리 통합 — (A) 사람 감지 정지 + (B) home_robot1 재측정·AMCL 리셋·유리 경유지 (done 2026-06-01)

> 1차 데모 직전 두 갈래 작업을 한 번호로 통합(중복 DEC-041 정리). **A**: 사람 감지 정지(2026-06-01), **B**: home_robot1 좌표/마커/유리 경유지 동기화(2026-05-29).

#### A. 사람 감지 정지 — YOLOv8 + Depth 게이팅 노드 + PersonClearCondition BT 플러그인 (2026-06-01)
- **Context**: 안내 주행 중 전방에 사람이 들어오면 정지하는 안전 기능. DEC-039에서 "향후 계획"으로 남긴 PersonClearCondition C++ BT 노드를 실제 구현. 학습 없이 YOLOv8n COCO 사전학습 모델 사용.
- **결정 1 — 패키지 분리 (`ulsan_person_detect` + `ulsan_bt_plugins`)**:
  - 처음엔 기존 `wego_aruco`(카메라 사용)에 사람 감지를 붙이는 안을 검토했으나, ArUco 마커 처리와 YOLO 사람 감지는 역할이 다름 → 패키지 응집도 위해 분리.
  - Python 추론 노드(`ulsan_person_detect`)와 C++ BT 플러그인(`ulsan_bt_plugins`)도 언어·실행 맥락(rclpy 노드 vs Nav2 pluginlib)이 달라 별도 패키지.
- **결정 2 — Depth 거리 게이팅 (0.7m)**:
  - RGB만 쓰면 화면에 잡히는 모든 사람(멀리 지나가는 사람 포함)에 정지 → 안내 로봇이 못 움직임.
  - YOLO 2D 박스 중심 40% 영역의 Depth 중앙값으로 거리 산출 → 0.7m 이내 사람만 정지 대상. (박스 중앙만 샘플링해 배경 픽셀 오염 방지, depth=0 무효 픽셀 제외)
  - depth 토픽 없으면 화면 감지만으로 보수적 정지(fail-safe).
- **결정 3 — BT 통합: ReactiveSequence + RUNNING 차단**:
  - `<ReactiveSequence>[PersonClearCondition, FollowPath]</ReactiveSequence>` 구조. 사람 감지 시 PersonClearCondition이 **RUNNING** 반환 → ReactiveSequence가 형제 FollowPath에 `halt()` → controller_server cancelGoal → cmd_vel 정지.
  - **FAILURE를 쓰지 않은 이유**: FAILURE면 RecoveryNode가 복구 동작(BackUp/ClearCostmap)을 발동 → 사람 앞에서 후진하는 오동작. RUNNING은 복구 미발동 + 단순 정지.
  - 정지 중에도 `PipelineSequence`가 ComputePathToPose 재계획을 계속 수행 → 사람이 벗어나면 최신 경로로 즉시 재개.
- **결정 4 — ConditionNode가 RUNNING 반환**:
  - BT.CPP v3에서 `ConditionNode`는 RUNNING 반환 허용(SyncActionNode는 `LogicError`로 금지) → 조건 노드 의미를 유지하면서 차단 구현.
  - ROS 연동은 Nav2 `IsBatteryLowCondition` 표준 패턴 채택: blackboard `"node"`로 공유 rclcpp 노드 획득 + 전용 callback group을 tick()에서 `spin_some()`으로 논블로킹 수집.
  - 라이브러리명 = `plugin_lib_names` 항목명 규칙 → `diff_navigation_params.yaml`에 `ulsan_person_clear_condition_bt_node` 등록해야 bt_navigator가 `.so` 로드.
- **결정 5 — numpy<2(1.26) 타깃**: 실행 데스크탑의 `cv_bridge`가 numpy 1.x로 컴파일됨(numpy 2.x에서 `imgmsg_to_cv2` → `_ARRAY_API not found`). ArUco 노드와 동일 런타임 공유 위해 코드를 numpy 1.26 기준으로 작성(numpy 2.x 전용 API 금지). ultralytics는 numpy≥1.23이라 호환.
- **변경 파일**: `ulsan_person_detect/`(신규 패키지, person_detect_node.py), `ulsan_bt_plugins/`(신규 패키지, person_clear_condition.{hpp,cpp}, CMakeLists), `wego_2d_nav/behavior_trees/navigate_to_pose_w_replanning_and_recovery.xml`, `navigate_through_poses_w_replanning_and_recovery.xml`, `wego_2d_nav/params/diff_navigation_params.yaml`
- **미완료**: 실기기 검증(사람 0.7m 진입→정지→이탈→재개), person_detect_node의 launch 통합(현재 수동 실행), 데스크탑 `pip install ultralytics`.
- **면접 어필**: "Nav2 BT에서 사람 감지 정지를 '복구를 유발하는 FAILURE'가 아니라 'RUNNING으로 형제 노드를 halt'하는 ReactiveSequence 패턴으로 설계해, 사람 앞에서 후진하는 오동작을 구조적으로 배제. RGB만으로는 멀리 지나가는 사람도 멈추는 문제를 Depth 거리 게이팅으로 해결. BT.CPP의 ConditionNode/SyncActionNode RUNNING 허용 차이까지 근거로 노드 베이스를 선택."

#### B. home_robot1 좌표 재측정 + AMCL 리셋 방식 변경 + 유리 구간 경유지 튜닝 (2026-05-29)

- **Context**: 마커 위치 이동 후 home_robot1 좌표, markers.yaml, target_dist, glass 경유지가 모두 구버전 값으로 남아있어 전체 동기화 필요. 또한 PBVS 도킹 후 AMCL 리셋이 yaw 140° 오차로 완전히 틀리는 문제 발견.
- **변경 1 — home_robot1 좌표 재측정**:
  - AMCL pose 실측: x=-0.1111, y=0.0123, yaw=-1.5708 (마커 정면 90° 확인)
  - home_robot1_staging: x=-0.1111 (동일), y=0.5123 (home 기준 +0.5m), yaw=-1.5708
  - staging x를 home과 동일하게 맞춰 PBVS 진입 시 정면 직진만으로 수렴 가능
- **변경 2 — markers.yaml ID 0 재캘리브레이션 + target_dist 동기화**:
  - 마커 위치: map_x=-0.0949, map_y=-0.7307, map_z=0.0786, qx=-0.0026, qy=0.7567, qz=0.6537, qw=-0.0059
  - aruco_pose_corrector로 실측한 camera depth=0.513m → target_dist 0.432→0.513
- **변경 3 — AMCL 리셋 방식 변경 (핵심)**:
  - 기존: 도킹 후 마커 rvec/tvec으로 T_map_base 역산 → /initialpose 발행
  - 문제: 단일 평면 마커 정면 근처에서 yaw 관측성(out-of-plane rotation) 낮음 → rvec 노이즈 → yaw 140° 오차 (실기기 확인: x=0.005, y=-0.114, yaw=+50.9° vs 예상 x=-0.111, y=0.012, yaw=-90°)
  - 결정: `_publish_initialpose()`에서 waypoints.yaml의 home_key 좌표 직접 발행. PBVS 성공 = 로봇이 home에 있다는 사실을 활용.
  - TF buffer/listener, _tf_to_matrix 제거. markers.yaml의 map_pose는 캘리브레이션 도구 전용으로만 유지.
  - **후속 (2026-06-01)**: 운영 경로에서 마커 맵 좌표를 전혀 안 쓰는 것이 확정되어 `markers.yaml`의 `map_x/y/z·map_q*·calibrated` 필드를 제거. 도킹 노드(`aruco_home_dock`)는 `size`+`home_marker`만 읽고, PBVS는 마커 상대 포즈만 사용하므로 죽은 데이터를 정리. `aruco_pose_corrector`는 calibration_mode(필드 미사용, 값 출력만)로 보존 — 필요 시 재측정 가능.
  - 면접 어필: "단일 평면 마커의 yaw 관측성 한계를 실기기 로그로 정량화(140° 오차)하고, 도킹 성공이라는 사실 자체를 AMCL 리셋 근거로 활용하는 방식으로 전환."
- **변경 4 — 유리 구간 경유지 튜닝**:
  - glass_entry: (0.0276, 2.486) → (-0.2, 2.65). 로봇 복도 주행 경로(x≈-0.1)에 맞게 조정
  - glass_exit: (2.471, 2.653) → (2.2158, 2.7579). 실측 재측정
  - RemovePassedGoals radius: 0.2 → 0.7. 경유지 0.2m 이내 미통과 시 제거 안 되어 로봇이 경유지로 되돌아가는 문제 해결
  - BackUp dist: 0.30 → 0.10m. 유리 구간 좁은 공간에서 0.3m 후진이 맵 경계 이탈 → "Pose Goes Off Grid" 해결
  - 유리 구간 경유지 통과 실기기 검증 완료
- **구현 위치 (B)**: `wego_behaviour/config/waypoints.yaml`(home_robot1/staging/glass), `wego_aruco/config/markers.yaml`(ID 0), `wego_aruco/launch/aruco_corrector_launch.py`(target_dist), `wego_aruco/wego_aruco/aruco_home_dock.py`(_publish_initialpose 재설계), `wego_2d_nav/behavior_trees/*.xml`(radius, backup_dist)

- **Date**: 2026-06-01 (A) / 2026-05-29 (B)

---

### DEC-040: 관제 GUI 시스템 상태 패널 연결 판단 방식 — ROS2 Diagnostics 표준 채택 (done 2026-05-29)
- **Context**: 관제 GUI 시스템 상태 패널에서 dispatcher/traffic 노드를 켜지 않아도 "연결됨"으로 표시되는 버그 발견. 기존 코드는 `get_topic_names_and_types()`로 `/limo1/goal_destination`, `/limo1/pause` 토픽 존재 여부로 연결을 판정했는데, GUI 자신이 시작 시 이 토픽들의 퍼블리셔를 생성하므로 항상 토픽이 존재 → 항상 연결됨으로 표시되는 구조적 결함.
- **Options**:
  - A) `count_publishers(topic) > 1` — GUI 자신 제외한 퍼블리셔 수 확인. 노드 등록 여부만 확인, 실제 데이터 기준 아님.
  - B) `get_node_names()` — 노드 프로세스 존재 여부 확인. 노드가 hang 걸려도 연결됨으로 표시.
  - C) Heartbeat 토픽 — 노드가 주기적으로 토픽 발행, GUI에서 수신 시간 체크. 구현 간단하나 비표준.
  - D) **ROS2 Diagnostics (`diagnostic_updater`)** — `/diagnostics` 토픽에 노드 상태 주기 발행. Nav2, MoveIt, ros2_control 등 ROS2 메이저 패키지 표준 방식.
- **Decision**: **D — ROS2 Diagnostics 표준 채택**
  - `wego_behaviour`, `wego_dispatcher`, `wego_traffic` 각 노드에 `diagnostic_updater.Updater` 추가
  - 각 노드가 `/diagnostics`에 1초 주기로 상태 발행 (`DiagnosticStatus.hardware_id` = 노드명)
  - `wego_behaviour`(domain 6/7): `bridge_robot.yaml`에 `/diagnostics` → `/ROBOT_NAME/diagnostics` 브릿징 추가
  - GUI `ros_node.py`: `/limo1/diagnostics`, `/limo2/diagnostics`, `/diagnostics` 구독 → `_diag_recv` 수신 시각 갱신
  - `is_connected()` → `is_node_ok(key)` 교체 — `_diag_recv[key]` 기준 5초 timeout
  - `map_view._check_connections()`: 기존 토픽 존재 체크 완전 제거, `is_node_ok()` 기반으로 교체
- **구현 시 발견된 버그**: `diagnostic_updater`가 발행하는 `DiagnosticStatus.name`은 `"hardware_id: task_name"` 복합 형식. `status.name`으로 매칭하면 항상 실패 → `status.hardware_id`로 매칭해야 함.
- **변경 파일**: `wego_behaviour/behaviour_node.py`, `wego_dispatcher/dispatcher_node.py`, `wego_traffic/traffic_node.py`, `wego_bridge/config/bridge_robot.yaml`, `ulsan_gui/ros_node.py`, `ulsan_gui/views/map_view.py`, 4개 `package.xml`
- **Rationale**:
  - topic existence 체크: GUI 자신이 퍼블리셔를 생성하면 항상 true → 구조적으로 올바른 연결 판단 불가
  - `count_publishers > 1` / `get_node_names()`: 실제 데이터 기준이 아닌 등록 여부만 확인
  - Diagnostics: 노드가 실제로 동작 중일 때만 주기 발행 → 데이터 수신 시간 기반 판단. Nav2 등 외부 패키지 상태도 추가 코드 없이 동일하게 모니터링 가능
- **면접 어필**: "ROS2 Diagnostics 표준 방식을 채택해 Nav2, MoveIt과 동일한 노드 헬스 모니터링 구조를 구현. topic 존재 여부라는 잘못된 지표 대신 실제 데이터 수신 시간 기반으로 판단 기준을 교체."
- **Date**: 2026-05-29

---

### DEC-039: Nav2 BT XML 커스텀 — GoalUpdated 제거 + 복구 행동 재설계 + navigate_to_pose 커스텀 추가 (done 2026-05-28)
- **Context**: Nav2 기본 BT XML 2개(navigate_to_pose, navigate_through_poses)를 분석하여 우리 프로젝트에 맞게 3가지 개선.
- **변경 1 — GoalUpdated 제거**:
  - 기존: `ReactiveFallback`의 첫 번째 자식으로 `GoalUpdated` 조건 노드 존재
  - 문제: `GoalUpdated`는 주행 중 새 goal이 들어오면 SUCCESS 반환해 복구 중단 용도. 우리 프로젝트는 goal을 출발 시 1회만 설정(`goToPose`/`goThroughPoses`)하고 절대 변경 안 함 → 항상 FAILURE → 사실상 dead code
  - 결정: 제거. `ReactiveFallback`에 `RoundRobin`만 남김
- **변경 2 — 복구 행동 재설계 (BackUp+ClearCostmap)**:
  - 기존: `ClearEntireCostmap → Spin(1.57rad) → Wait(5s) → BackUp(0.3m)` 순서
  - 문제: 유리 난반사 phantom 장애물이 주요 실패 원인. 유리와 가까울수록 LiDAR 빔이 더 넓은 각도로 난반사 → phantom 증가. `Spin`은 새로운 각도 난반사 유발 → 오히려 phantom 악화. `ClearEntireCostmap`은 유리 근처에서 즉시 재생성. `BackUp`이 유리에서 멀어지게 해 phantom 감소.
  - 결정: `Spin` 제거, `BackUp → ClearLocal → ClearGlobal`을 Sequence로 묶어 한 세트 실행 후 `Wait`으로 폴백
    ```xml
    <RoundRobin>
      <Sequence name="BackUpAndClear">
        <BackUp backup_dist="0.30" backup_speed="0.05"/>
        <ClearEntireCostmap (local)/>
        <ClearEntireCostmap (global)/>
      </Sequence>
      <Wait wait_duration="5"/>
    </RoundRobin>
    ```
  - BackUp이 실제 장애물에도 안전한 이유: 장애물 반대 방향으로 이동 → 충돌 없음
- **변경 3 — navigate_to_pose 커스텀 파일 추가**:
  - 기존: `navigate_to_pose`는 Nav2 기본값(`/opt/ros/humble/...`) 사용. `navigate_through_poses`만 커스텀 관리
  - 결정: `wego_2d_nav/behavior_trees/navigate_to_pose_w_replanning_and_recovery.xml` 신규 생성. 변경 1·2 동일 적용. `navigation_only_launch.py`에 `default_nav_to_pose_bt_xml` 오버라이드 추가
  - 이유: 두 BT가 같은 복구 정책을 공유해야 일관성 유지. wego_2d_nav 패키지에서 단일 관리
- **RemovePassedGoals 분리 (기존 작업, navigate_through_poses 전용)**:
  - Nav2 기본값: `RemovePassedGoals`가 `RateController(0.333Hz)` 안 → 3초에 1번 경유지 통과 체크
  - 변경: `PipelineSequence` 직속 자식으로 분리 → 매 틱 체크 → glass_entry/exit 통과 즉시 제거
  - `navigate_to_pose`는 단일 목적지라 `RemovePassedGoals` 해당 없음
- **향후 계획 — PersonClearCondition 커스텀 C++ BT 노드**:
  - 사람 감지 정지 기능을 위한 커스텀 조건 노드. 사람 감지 구현(YOLO 모델 선택) 후 진행
  - 구조: `ReactiveSequence` → [PersonClearCondition, RecoveryNode(FollowPath)]
  - 반환값: 사람 없음 → SUCCESS, 사람 감지 → RUNNING (FAILURE 없음 — 복구 동작 미발동)
  - 경로 재계획(ComputePathThroughPoses)은 RUNNING 중에도 PipelineSequence에 의해 계속 실행됨
- **구현 위치**: `wego_2d_nav/behavior_trees/`, `wego_2d_nav/launch/navigation_only_launch.py`
- **면접 어필**: "Nav2 기본 BT XML의 GoalUpdated가 우리 프로젝트에서 항상 FAILURE임을 소스코드 분석으로 확인하고 제거. 유리 난반사의 물리적 특성(근거리일수록 phantom 증가)을 분석해 Spin 제거 + BackUp 선행 복구 정책 설계. 두 BT XML을 wego_2d_nav 패키지에서 통합 관리."
- **Date**: 2026-05-28

---

### DEC-038: PBVS 홈 도킹 제어기 재설계 — 극좌표 vs 단계분리 비교 후 staged 채택 (done 2026-05-26)
- **Context**: 기존 `aruco_home_dock`의 3DOF 제어가 목표 근처에서 수렴 실패. `angular.z = -Kp_w·lateral - Kp_yaw·yaw_error`로 lateral·yaw 보정을 단순 합산했는데, 실기기 로그에서 두 항이 ω 하나를 공유하며 서로 상쇄(fight)하는 것을 확인. depth=0.279m에서 v≈0.002, w≈-0.002로 교착 → 도킹 타임아웃.
- **근본 원인 진단**: 차동구동(비홀로노믹) 로봇은 제어 입력 (v, ω) 2개인데 도킹 목표는 depth·lateral·yaw 3개 → **과소구동(underactuated) 자세 정밀화 문제**. 옆으로 평행이동(strafe)이 불가능해 lateral을 고치려면 반드시 ω로 회전해야 하고, 그게 yaw 보정과 충돌. 두 오차를 독립적으로 0에 보낼 수 없음.
- **공통 해법**: lateral·yaw를 따로 더하지 말고, **도킹 목표점(마커 법선 위 target_dist 지점)의 로봇 기준 기하 (ρ, α, θ_g)** 로 통합. `_compute_geometry()`가 마커 위치 + 법선으로 셋을 산출.
- **A/B 두 제어기 구현 + 실기기 비교** (`dock_mode` 파라미터로 전환):
  - **A) 극좌표 자세 제어기** (`_ctrl_polar`, Lyapunov 안정, Siegwart 3.6.2.4): `v=k_ρ·ρ, ω=k_α·α+k_β·β`. 결과: 수렴은 하나(lateral 1.4cm) **ω가 ±0.3에 상시 포화 → 심한 S자 사행**. 노이즈 심한 마커 법선을 고게인(k_α=2.0)으로 추종한 게 원인.
  - **B) 단계 분리** (`_ctrl_staged`, turn→drive→turn): 조준 회전 → 직진(+약한 조향) → 정면 정렬. 결과: **매끄럽고 포화 없음**, lateral 0.8~1.7cm. 채택.
- **Decision**: **방법 B (staged) 채택.** 안정적인 lateral(위치)은 직진으로, 자세는 단계 회전으로 분리하면 노이즈 심한 마커 법선에 과민반응하지 않음.
- **추가 문제 — 목표 근처 α 폭발**: staged phase 1의 조향 `kp_steer·α`에서 `α=atan2(Ty,Tx)`가 ρ→0일 때 분자·분모 모두 0에 수렴해 노이즈로 폭발(ρ=0.06m, lat 4cm → α=35.8°). 마지막 순간 급조향(머리 틀림)으로 yaw가 -90°를 15° 초과. **해결**: `ρ < steer_freeze(0.15m)` 구간은 조향 끄고 직진만(lateral 잔차 수용). 차동구동은 마지막 6cm에서 4cm lateral을 급회전 없이 못 지우므로 잔차를 받아들이는 게 옳음.
- **단일 평면 마커 한계 확인**: 정면 근처에서 마커 법선(out-of-plane 회전) 관측성이 낮아 θ_g 신뢰 제한 → 로봇이 비스듬히 멈춰도 θ_g≈0으로 오판(실기기에서 AMCL 리셋 yaw가 -47°·-61°·132° 등으로 흔들림). staged가 lateral 위주 제어로 우회. 더 높은 정밀도 필요 시 **마커 2개 자세 삼각측량** 권장(미적용, 향후 과제).
- **부수 작업**: 마커 이동 후 재캘리브레이션(markers.yaml ID 0, std 0.0002로 안정), `target_dist` 0.271→0.432, `home_robot1_staging` x=-0.13 보정, PBVS 속도 0.15→0.08m/s.
- **구현 위치**: `wego_aruco/aruco_home_dock.py` (`_compute_geometry`, `_ctrl_polar`, `_ctrl_staged`), `aruco_corrector_launch.py` (`dock_mode` 런치 인자)
- **면접 어필**: "도킹 수렴 실패를 비홀로노믹 과소구동 문제로 진단. 단순 합산 P제어가 lateral·yaw를 ω 하나로 충돌시킨다는 걸 로그로 확인하고, 목표점 기하(ρ,α,θ_g)로 통합. Lyapunov 극좌표 제어와 단계분리 제어를 둘 다 구현해 실기기 비교 후, 노이즈 심한 단일 마커 법선 환경에선 단계분리가 우월함을 입증. 목표 근처 atan2 특이점(α 폭발)까지 잡아 정밀 정차 달성."
- **후속**: 2026-06-01 A/B 실험 종료 — polar 제어기 코드 제거, staged 단독 채택 (DEC-042 참고).
- **Date**: 2026-05-26

---

### DEC-037: 홈 출발 180° 회전 문제 — Spin 선실행 + SimpleProgressChecker 복원 (done 2026-05-25)
- **Context**: PoseProgressChecker(`required_movement_angle: 0.5rad`) 적용으로 홈 출발 180° 회전 시 `Failed to make progress`는 해결됐으나, 부작용 발견. PoseProgressChecker는 각도 변화도 "진행"으로 인정하므로, 주행 중 로봇이 제자리 회전하며 실제로 stuck된 상황에서도 실패 판정이 내려지지 않음 → 복구 동작(recovery) 미발동 → stuck 방치 위험.
- **Options**:
  - A) PoseProgressChecker 유지 — 홈 출발은 해결되나 주행 중 stuck 감지 정확도 희생
  - B) Spin 선실행 + SimpleProgressChecker 복원 — 홈 출발 전 미리 회전, 주행 중 stuck 감지는 SimpleProgressChecker로 정확히 유지
- **Decision**: **방법 B — Spin 선실행 + SimpleProgressChecker 복원**
  - `IdleState`: 목적지 수신 시 `blackboard['from_home'] = True` 설정
  - `GuidingState`: `from_home=True`이면 `navigator.spin(math.pi)` 선실행 후 `from_home=False` 초기화
    - Spin 중 abort/pause 처리 — abort: RETURNING 전환, pause: WAITING 전환 (재개 시 재Spin 없음)
    - Spin 실패 시 graceful degradation — 경고 로그 후 주행 계속
  - `diff_navigation_params.yaml`: `PoseProgressChecker` → `SimpleProgressChecker` 복원, `required_movement_angle` 제거
- **Rationale**:
  - PoseProgressChecker는 "회전해도 괜찮아"라는 패치. Spin은 "회전을 미리 끝내고 출발"이라는 근본 해결
  - AMCL 파티클 수렴 부수 효과: 홈 출발 직전은 AMCL drift 가능성이 가장 높은 시점. Spin 중 다양한 각도 LiDAR 스캔 수집 → 파티클 수렴 가속. 상용 AMR이 초기화 시 제자리 회전으로 localization을 안정화하는 것과 동일 원리
  - SimpleProgressChecker 복원으로 주행 중 stuck 감지 정확도 회복 → 복구 동작 정상 발동
  - PoseProgressChecker는 "홈 출발 문제" 해결을 위해 "전체 주행 구간 stuck 감지"를 희생하는 트레이드오프가 나쁨
- **구현 위치**: `wego_behaviour/states.py` (IdleState, GuidingState), `wego_2d_nav/params/diff_navigation_params.yaml`
- **면접 어필**: "PoseProgressChecker로 회전을 '진행'으로 인정하는 패치 대신, 홈 출발 전 Spin으로 회전을 선처리하는 방식을 선택. 주행 중 실제 stuck 감지 정확도를 희생하지 않으면서 출발 문제를 근본적으로 해결. Spin이 AMCL 파티클 수렴을 돕는 부수 효과도 취득."
- **Date**: 2026-05-25

---

### DEC-036: FAILED 미션 통계 분리 — dispatcher 상태 시퀀스 추론 (done 2026-05-22)
- **Context**: GUIDING 실패 후 FAILED → RETURNING → IDLE 시퀀스를 거쳐 홈으로 복귀하는데, 기존 `wego_dispatcher._check_completions`는 "ACTIVE 미션의 로봇이 IDLE이면 완료"로만 판정. 정상 완료와 실패 후 복귀를 구분 없이 `PATCH /assign/{id}/complete`로 일괄 처리 → DB logs 테이블에 모든 미션이 `mission_complete`로만 기록되어 **임무 실패가 임무 완료로 둔갑하는 문제**.
- **Options**:
  - A) wego_behaviour가 FAILED 진입 시 `/limo[12]/mission_failed` 별도 토픽 발행 → dispatcher 구독
  - B) dispatcher가 기존 `/robot_status` 시퀀스에서 FAILED를 감지해 `_failed` set으로 추적
- **Decision**: **방법 B — 상태 시퀀스 추론**
  - `dispatcher_node`에 `_failed: set[int]` 추가
  - `_status_cb`에서 FAILED 상태 진입 시 해당 로봇의 active 미션을 `_failed`에 등록
  - `_check_completions`에서 IDLE 복귀 감지 시 `_failed`에 있으면 `PATCH /assign/{id}/fail` 호출
  - FastAPI에 `fail_mission` 엔드포인트 신규 — mission.status는 COMPLETED로 마킹하되 logs에 `mission_fail` 타입 기록
- **Rationale**:
  - 방법 A는 wego_behaviour + wego_bridge + dispatcher + FastAPI 4곳 수정 필요 → 실기기 테스트 부담
  - dispatcher가 이미 `/robot_status`를 구독 중이고, robot_status는 1초 주기로 재발행되므로 FAILED 한 번도 못 보고 지나갈 가능성 매우 낮음
  - mission.status는 COMPLETED로 유지하고 logs 타입만 분리 → DB 스키마 변경 없음, 기존 카운트 함수 영향 없음
- **GUI abort와의 차이**: GUI 강제 abort는 RETURNING으로 직접 전이(FAILED 미경유)하므로 자동으로 `/complete`로 잡힘. abort 자체는 이미 이벤트 로그에 별도 기록되니 중복 없음.
- **면접 어필**: "FSM 상태 시퀀스를 dispatcher가 추적해 별도 토픽 없이 통계 분리 달성. 단순함과 확장성 간 트레이드오프 판단을 명확히 보여줄 수 있는 사례."
- **Date**: 2026-05-22

---

### DEC-035: 관제 GUI 확장성 리팩토링 — ROBOTS 단일 정본 + 통합 시그널 (done 2026-05-22)
- **Context**: 기존 `ulsan_gui` 코드 전반에 `'limo1'`/`'limo2'` 하드코딩이 산재. `GuiSignals`는 `sig_status_1`/`sig_status_2`처럼 숫자 suffix로 시그널을 분리해놨고, `ros_node`는 5개의 분산 dict(`latest_status`, `_prev_status`, `latest_pose`, `latest_dest`, `_last_recv`)에 같은 키를 박아둠. 로봇을 추가하려면 8개 시그널 정의 + 5개 dict + 모든 뷰의 if 분기 등 수십 곳을 동시 수정해야 하는 구조.
- **Decision**: **ROBOTS 튜플 단일 정본 + RobotState dataclass + 통합 시그널**
  - `ros_node.ROBOTS: tuple[str, ...] = ('limo1', 'limo2')` — 단일 정본
  - `robot_label(robot)` 헬퍼 — `'limo1'` → `'LIMO 1'` 동적 변환
  - `@dataclass RobotState` — 5개 분산 dict를 `self.robots: dict[str, RobotState]`로 통합
  - `GuiSignals`: `sig_status_1/2` 등 8개 분리 시그널 → `sig_status(robot, status)` 등 5개 통합 시그널
  - 모든 뷰: 탭/카드/시스템 상태/통계 칩이 `for robot in ROBOTS:` 루프로 동적 생성
  - 색상 팔레트: 인덱스 기반 순환(`_ROBOT_COLORS[i % len(_ROBOT_COLORS)]`)
- **Rationale**:
  - pyqtSignal은 클래스 변수라 동적 추가 불가 → `(robot, value)` 파라미터 방식으로 통합 필수
  - 같은 키를 5개 dict에 분산하는 패턴은 의미적으로 "로봇 한 마리"가 한 단위로 묶이지 못한 결과 → dataclass 한 객체로 묶음
  - 로봇 추가 시 ROBOTS 튜플 한 줄 수정으로 GUI 전체 자동 확장
- **부수 정리 (같이 진행)**:
  - 공통 `HttpGetThread` 클래스 신규 — 3개 HTTP 스레드 클래스 중복 제거
  - `_FastApiChecker`를 `MapView.__init__`에서 1회 생성 후 재사용 (2초마다 객체 재생성 → 단일 인스턴스)
- **백엔드 확장성**: FastAPI(`routers/robots.py`, `_pick_idle_robot`, `count_today_missions_by_robot`)와 `wego_dispatcher`, `wego_traffic`은 여전히 2대 전용 — **데모 후 작업**으로 보류
- **면접 어필**: "GUI에서 ROBOTS 튜플 한 줄로 N대 로봇 자동 확장. pyqtSignal 클래스 변수 제약 하에서 통합 시그널 + 파라미터 필터링 패턴으로 해결. dataclass로 도메인 모델 응집도 확보."
- **Date**: 2026-05-22

---

### DEC-034: 관제 GUI 로그 아키텍처 — 이벤트 로그 vs 미션 로그 분리 (done 2026-05-22)
- **Context**: 관제 GUI에 로그성 위젯이 3곳(지도 뷰 미니 이벤트 로그, 로봇 뷰 "오늘 이벤트", 로그 뷰 미션 로그) 존재. 각자 데이터 소스·필터링 조건이 다른데 명확한 역할 분리가 없었고, 로봇 뷰 "오늘 이벤트"는 `sig_status_1/2`에서 상태 변화 필터 없이 매번 `_add_event` 호출 → robot_status가 1초 주기로 재발행되며 같은 상태가 1초마다 누적되는 버그. 또한 FastAPI logs 테이블에는 노쇼 감지만 들어가고 임무 시작/완료 로그는 누락 상태.
- **Decision**: **이벤트 로그(GUI 조작) ↔ 미션 로그(방문자 UI 임무) 명확 분리**
  - **이벤트 로그** (메모리, GUI 세션만): 관제 GUI에서 발생한 모든 조작
    - 상태 전이 (IDLE/BUSY/RETURNING/WAITING/FAILED)
    - 긴급 제어 (일시정지/재개/임무중단)
    - 수동조작 전환/복귀
    - 지도 뷰: 두 로봇 통합 표시
    - 로봇 뷰: `sig_gui_log` 필터링으로 해당 로봇 개별 표시
  - **미션 로그** (DB 영구 저장, 로그 뷰): 방문자 UI를 통한 임무 흐름
    - 예약 체크인 배정 → `mission_start`
    - 강의실 안내 배정 → `mission_start`
    - 현장방문 배정 → `mission_start`
    - 임무 완료 → `mission_complete`
    - 임무 실패(FAILED 거침) → `mission_fail` (DEC-036)
    - 노쇼 감지 → `noshow` (APScheduler)
- **구현**:
  - `robot_view._on_status`에서 무조건 `_add_event` 호출 제거
  - `RobotPanel._connect_signals`에 `sig_gui_log` 연결 추가, `_on_gui_log`에서 robot_label 비교로 필터링
  - FastAPI `assign.py` 3곳, `walkin.py` 1곳에 `create_log` 호출 추가
  - `LOG_TYPE_COLOR`를 `ulsan_gui/styles.py` 단일 정본으로 통합 (3개 파일 중복 제거)
- **부수 버그 수정**:
  - `_STATUS_LOG_TYPE`의 `'ERROR'` → `'FAILED'` (mission_fail 로그가 발화되지 않던 죽은 매핑)
  - `robot_view` STATUS_COLOR/STATUS_BG에 FAILED 누락 추가 (회색 UNKNOWN으로 표시되던 버그)
- **Rationale**:
  - 두 로그의 시간 스케일·범위·저장 정책이 본질적으로 다름 (실시간 조작 추적 vs 영구 비즈니스 기록)
  - 같은 정보를 3곳에 중복 표시하는 대신 책임을 분리 → 정보 가치 명확화
  - mission_fail 로그가 발화되지 않던 정합성 버그(ERROR ≠ FAILED)를 동시 해결
- **면접 어필**: "로그성 위젯의 역할을 시간 스케일·범위·저장 정책 기준으로 분리. 비즈니스 데이터(미션)와 운영 데이터(GUI 조작)를 다른 계층에서 관리하는 설계 원칙 적용."
- **Date**: 2026-05-22

---

### DEC-033: GUIDING 실패 처리 — FAILED 상태 추가 (done 2026-05-21)
- **Context**: 현재 GuidingState에서 Nav2가 SUCCEEDED가 아닌 결과를 반환하면 바로 IDLE로 전환. 두 가지 문제: ① 실패한 위치(복도 중간 등)에서 IDLE이 되어 dispatcher가 즉시 재배정 가능 — 로봇이 홈 아닌 위치에서 새 임무를 받는 위험. ② IDLE과 실패를 관제 UI에서 구분 불가.
- **Decision**: **GUIDING failed → FAILED 상태 → RETURNING**
  - `FailedState`: `robot_status='FAILED'` 발행 + TTS "오류가 발생하여 안내에 실패했습니다. 현재 위치에서 관리자를 기다려 주세요." + 10초 대기 → `'return_home'` 반환
  - FSM: `GUIDING 'failed' → FAILED`, `FAILED 'return_home' → RETURNING`
  - 관제 UI: FAILED 빨간 색상 추가 (`#dc2626`)
- **TTS 내용 선택 이유**: "홈으로 복귀합니다"는 방문자를 혼란 없이 남겨두는 문제. "관리자를 기다려 주세요"로 방문자에게 다음 행동을 안내하고, 10초 대기로 관제자가 현장 이동할 여유를 확보.
- **Rationale**:
  - 실패 후 항상 홈 복귀 → dispatcher가 로봇 위치를 신뢰 가능 (IDLE = 홈에 있음 보장)
  - 10초 FAILED 표시 → 관제자 인지 + 현장 이동 여유
  - "실패 시 원점 복귀"는 서비스 로봇 표준 패턴 (Kiva, Fetch, MiR 동일)
- **면접 어필**: "FSM 상태 설계 시 실패 처리를 별도 상태로 분리해 위치 신뢰성과 관제 가시성을 동시에 확보. TTS를 방문자 UX 관점에서 설계해 로봇 실패 상황에서도 방문자 혼란을 최소화."
- **Date**: 2026-05-21

---

### DEC-032: abort(임무 중단) 기능 설계 — /abort 전용 토픽 (done 2026-05-21)
- **Context**: 관제 UI의 🛑 임무중단 버튼이 `goal_destination`에 `home_key`를 발행하는 방식으로 구현되어 있었음. 두 가지 문제: ① FSM 상태와 무관하게 동작 — WAITING 중이면 home 목적지를 가이딩 목적지로 인식해 IDLE 이후 다시 홈으로 안내하는 오동작 가능. ② IDLE/RETURNING 상태에서도 적용되어 불필요한 임무 시작.
- **Decision**: **`/abort` 전용 토픽 + FSM 상태별 처리**
  - **GUIDING**: `navigator.cancelTask()` → `'aborted'` → RETURNING
  - **WAITING** (return_to='GUIDING'): `_abort_flag` 감지 → `blackboard['return_to'] = 'RETURNING'` (WAITING 유지, resume 후 RETURNING으로 복귀)
  - **WAITING** (return_to='RETURNING'): 무시 (이미 복귀 예정)
  - **IDLE / RETURNING**: 무시
- **구현**:
  - `behaviour_node.py`: `/abort` 구독, `_abort_cb`, FSM `'aborted': 'RETURNING'` 전환 추가
  - `states.py`: GuidingState abort 우선 체크(pause보다 앞), WaitingState abort 루프 내 처리
  - `bridge_robot.yaml`: `/ROBOT_NAME/abort` 브릿지 (domain 5→LIMO)
  - `ros_node.py`: `_abort_pubs`, `publish_abort()`
  - `map_view.py`: `_send_abort_home()` → `publish_abort()` 호출로 변경
- **Rationale**:
  - WAITING 상태에서 즉시 RETURNING이 아니라 `return_to`를 변경하는 이유: wego_traffic이 resume을 보낼 때까지 기다려야 함. 즉시 복귀하면 상대 로봇과 충돌 위험.
  - abort 전용 채널 분리로 각 FSM 상태가 의미있는 처리 가능.
- **면접 어필**: "abort 신호를 goal_destination 재사용이 아닌 전용 채널로 분리하여, FSM 각 상태가 맥락에 맞는 처리를 할 수 있게 설계. WAITING 중 abort 시 즉시 전환하지 않고 충돌 회피 우선순위를 유지하는 부분이 핵심."
- **Date**: 2026-05-21

---

### DEC-031: 홈 출발 시 Failed to make progress — PoseProgressChecker 교체 (done 2026-05-21)
- **Context**: home1에서 classroom 목적지로 출발 시 로봇이 180° 제자리 회전 필요. 이 과정에서 `Failed to make progress` 반복 발생. Nav2가 recovery(ClearEntireCostmap)를 최대 6회 반복하며 각 시도마다 10초씩 소요.
- **원인 분석**:
  - `SimpleProgressChecker`는 선형 이동 거리만 측정. 제자리 회전(각도 변화)을 진행으로 인식 안 함
  - `movement_time_allowance=10s` 안에 `required_movement_radius=0.5m` 미달 → 실패 판정
  - 타임스탬프 정밀 분석으로 확인: `Received a goal` → `Failed to make progress` 정확히 10.0초
  - `Passing new path to controller` (1.3초 간격)는 BT `RateController(hz=0.769)`의 주기적 리플랜이며 progress checker 타이머를 리셋하지 않음 (새 action goal 수신 시에만 리셋)
  - Recovery: `RecoveryNode(number_of_retries=6)` → `RoundRobin` → `ClearEntireCostmap` → 재시도 반복
- **Nav2 BT 실행 흐름**:
  ```
  RecoveryNode (최대 6회 재시도)
  ├── PipelineSequence (메인 주행)
  │   ├── RateController(hz=0.769) → ComputePathToPose  ← 1.3초마다 리플랜
  │   └── FollowPath  ← SimpleProgressChecker 10초 만료 → FAILURE
  └── RoundRobin (recovery)
      ├── ClearEntireCostmap (1번째)
      ├── Spin (2번째)
      ├── Wait (3번째)
      └── BackUp (4번째)
  ```
- **Decision**: **`PoseProgressChecker`로 교체** (revert 후 재적용 2026-05-21)
  - `required_movement_radius: 0.5` OR `required_movement_angle: 0.5rad(≈28°)` 중 하나 만족 시 진행 인정
  - 180° 회전 시작 직후 각도 조건 통과 → 실패 없이 주행 시작
- **Rationale**:
  - `SimpleProgressChecker`: 직선 주행에 적합. 출발 방향이 goal 방향과 반대인 경우 회전 구간에서 구조적 실패
  - `PoseProgressChecker`: 위치 + 방향 변화를 모두 측정 → 회전 중에도 진행으로 인정. home1 출발 시나리오에 적합
  - `movement_time_allowance` 단순 증가는 근본 해결이 아님. 회전이 느린 경우 또는 다른 시나리오에서 동일 문제 재발 가능
- **면접 어필**: "Nav2 `SimpleProgressChecker`가 선형 이동만 측정하는 설계 특성으로 인해, 출발 방향과 반대 방향으로 향하는 로봇이 회전 구간에서 반복 실패하는 문제를 타임스탬프 분석으로 정확히 진단. BT 구조(RecoveryNode, RateController)와 progress checker의 상호작용을 추적하여 `PoseProgressChecker` 교체로 해결."
- **Date**: 2026-05-19 (분석 완료, 적용 예정)

---

### DEC-030: 유리 구간 keepout 경계 hugging 해결 — NavigateThroughPoses + 경유 포인트 2개
- **Context**: Keepout Filter 적용 후에도 global planner가 keepout 경계 바깥의 cost가 0에 가까워 경계에 최대한 붙는 최단 경로를 생성. 경계 근처 주행 중 일부 진입하는 문제 발생.
- **Decision**: **NavigateThroughPoses + glass_entry / glass_exit 경유 포인트 삽입**
  - 통유리 사이 수직선의 양 끝에 경유 포인트 2개 측정·등록
  - 유리 구간 통과 목적지(상담실·카운터·멀티룸·회의실): `goThroughPoses([glass_entry, glass_exit, 목적지])`
  - classroom_1~5: 유리 구간 미통과 → 기존 `goToPose` 유지
  - 복귀 시 순서 반전: `goThroughPoses([glass_exit, glass_entry, home])`
  - 경유 포인트 yaw: 0.0 — 경유지는 goal checker 미적용, 위치만으로 방향 제약
- **NavigateThroughPoses 선택 이유**:
  - WaypointFollower: 내부적으로 NavigateToPose 반복 → 경유지마다 완전 정지. 유리 구간 한가운데 정지 발생
  - NavigateThroughPoses: 모든 경유지를 포함한 단일 전역 경로 생성 → 정지 없이 부드럽게 통과
  - 다른 BT XML(`navigate_through_poses_w_replanning_and_recovery.xml`) 로드
- **구현 위치**: `wego_behaviour/states.py` — `_needs_glass_via()`, GuidingState, ReturningState
- **Rationale**: "keepout 경계 hugging은 global planner의 cost 최소화 특성에서 비롯된 구조적 문제. 알려진 위험 구간에 강제 경유 포인트를 삽입해 경로를 명시적으로 제약하는 방식은 현업 AMR 표준 패턴."
- **면접 어필**: "keepout 경계에 붙어 주행하는 문제를 플래너 cost 구조로 진단하고, NavigateThroughPoses로 유리 구간 중앙 통과를 강제하는 경로 제약을 설계했습니다. WaypointFollower 대비 단일 전역 경로 생성으로 정지 없는 자연스러운 통과를 보장합니다."
- **미완료**: glass_entry / glass_exit 실측 좌표 입력 필요
- **Date**: 2026-05-19

---

### DEC-029: 홈 복귀 정밀 제어 방식 — 벽 마커 + PBVS (staging pose 방식)
- **Context**: 복도 구간 AMCL y drift로 인해 Nav2가 실제 홈 미도달 위치에서 false goal 판정하는 문제 확인. 로봇이 복도에서 홈 방향으로 주행 시 특징점 없는 복도만을 보고 y좌표를 홈에 도달했다고 추정. x,y가 tolerance(±10cm Euclidean) 안에 들어오면 Nav2가 goal 판정 후 yaw 회전 → 그제야 AMCL이 보정되지만 이미 틀린 위치에서 멈춘 상태.
- **Decision**: **벽 마커 + PBVS (Position-Based Visual Servoing) — staging pose 전환 방식**
  1. Nav2가 홈 전방 staging pose까지 주행 (xy_goal_tolerance 넓게 설정, AMCL 오차 흡수)
  2. Nav2 goal 완료(정지 상태) → 마커 기반 P제어로 전환
  3. 선속도 + 각속도 동시 발행: `angular = Kp_w × pixel_error_x`, `linear = Kp_v × (depth - target)`
  4. 로봇이 호(arc) 경로로 마커 정면에 수렴하며 접근 → 홈 정밀 정차
- **마커 위치**: 바닥 아님, **벽 부착** — 전방 카메라로 멀리서부터 감지 가능, FOV 유지
- **PBVS 선택 이유**:
  - 단순 이미지 P제어: x오프셋이 있으면 대각선 접근 문제
  - 제자리 회전 후 전진: 회전 중 마커 FOV 이탈 문제
  - 선속도+각속도 동시 제어: arc 경로로 마커가 항상 FOV 내 유지 + x오프셋 자동 수렴
- **staging 방식 선택 이유**: 마커 감지 즉시 전환(방법 1) vs staging pose 후 전환(방법 2)
  - 방법 1: Nav2 cancel 타이밍 불안정, 로봇 주행 중 P제어 초기 조건 불안정
  - 방법 2: Nav2 goal 완료 후 정지 상태에서 전환 → 안정적. opennav_docking 표준 패턴과 동일
- **구현 위치**: `wego_behaviour` ReturningState + 신규 `aruco_home_dock.py` 노드
- **구현 현황 (2026-05-19)**:
  - `wego_aruco/aruco_home_dock.py` 신규 작성 — `/aruco_home_dock` (std_srvs/Trigger) 서비스
  - `wego_behaviour` ReturningState: Nav2 staging 도착 후 `call_home_dock()` 호출
  - `aruco_corrector_launch.py`: aruco_home_dock 노드 추가
  - 미완료: target_dist 실측 (로봇을 home에 두고 `/aruco_debug` depth 값 확인), markers.yaml 재측정
- **Rationale**: "AMCL 기반 goal 판정의 구조적 한계를 실기기에서 확인. 마지막 구간만 절대 기준(마커 비전)으로 제어 전환하는 Coarse-to-Fine 패턴 적용. AMCL 정확도와 무관하게 홈 복귀 보장."
- **면접 어필**: "복도 AMCL drift로 인한 false goal 판정 문제를 실기기에서 진단. Nav2의 확률적 위치추정 한계를 마커 절대 기준으로 보완하는 계층적 제어 구조를 설계."
- **Date**: 2026-05-18

---

### DEC-028: domain bridge 실행 위치 — LIMO 도메인(6/7)에서 실행, 단일 템플릿 yaml
- **Context**: 기존 wego_bridge는 관제 노트북(domain 5)에서 bridge_limo1.yaml, bridge_limo2.yaml 2개를 실행하는 구조. 두 가지 문제 확인.
  1. **생명주기 불일치**: LIMO 시스템이 죽어도 domain 5의 브릿지 프로세스는 살아있어 domain 5에 stale 데이터 잔류 → 연결 끊김 감지 불가
  2. **yaml 중복**: bridge_limo1.yaml과 bridge_limo2.yaml이 도메인 번호와 토픽 prefix만 다른 중복 구조 → 로봇 추가 시 파일 증가
- **Decision**: **LIMO 도메인(6/7)에서 실행 + 단일 bridge_robot.yaml 템플릿**
  - `bridge_robot.yaml`: ROBOT_DOMAIN, ROBOT_NAME 플레이스홀더 템플릿
  - `bridge_launch.py`: OpaqueFunction으로 ROS_DOMAIN_ID 읽어 치환 후 tempfile 전달 (DEC-007 패턴)
  - robot_config.yaml에서 도메인→robot_name 매핑 참조 (단일 정본)
- **실행**:
  ```bash
  export ROS_DOMAIN_ID=6 && ros2 launch wego_bridge bridge_launch.py  # LIMO 1
  export ROS_DOMAIN_ID=7 && ros2 launch wego_bridge bridge_launch.py  # LIMO 2
  ```
- **Rationale**:
  - **생명주기 일치**: LIMO 도메인 시스템 종료 시 브릿지도 함께 종료 → domain 5가 연결 끊김 즉시 감지 (추후 관제 UI 연결 상태 모니터링에 활용 가능)
  - **단일 템플릿**: yaml 파일 1개로 모든 로봇 적용. 로봇 추가 시 robot_config.yaml + waypoints.yaml만 수정
  - **일관성**: localization_launch.py, behaviour_node.py와 동일한 ROS_DOMAIN_ID 기반 자동 결정 패턴
- **면접 어필**: "브릿지 생명주기를 LIMO 도메인과 일치시켜 연결 상태 감지를 구조적으로 보장. 단일 템플릿으로 확장성 확보."
- **Date**: 2026-05-14

---

### DEC-027: 방문자 UI 아키텍처 — 태블릿 웹앱 + wego_dispatcher (rosbridge 제거)
- **Context**: 기존 DEC-026에서 결정한 "LIMO 탑재 터치 UI + rosbridge" 방식의 두 가지 문제 발견.
  1. **UX 문제**: LIMO가 낮아(바닥에서 약 30cm) 방문자가 숙여서 입력해야 함.
  2. **설계 문제**: rosbridge를 통해 태블릿 JS가 직접 `/goal_destination`을 발행하는 구조 → 로봇 제어 로직이 브라우저에 있는 잘못된 설계.
- **Decision**: **태블릿(눈높이) 웹앱 + HTTP only + wego_dispatcher(rclpy 노드)**
  | UI | 스택 | 실행 위치 |
  |----|------|-----------|
  | 관제 GUI | PyQt + rclpy | 관제 노트북 (domain 5) |
  | 방문자 UI | React (HTTP only) | 태블릿 브라우저 → `http://192.168.0.115:3000` |
  | 웹 예약 UI | React | 관제 노트북 (포트 3001) |
  - `wego_dispatcher` (rclpy 노드, domain 5): FastAPI 폴링 → 로봇에 goal/speak 발행
  - 태블릿은 FastAPI HTTP만 사용. rosbridge 완전 제거.
- **Rationale**:
  - **rosbridge 제거**: 로봇 제어 로직(어느 로봇에 배정할지, goal 발행)이 ROS 노드(wego_dispatcher) 안에 있어야 함. 브라우저 JS에서 ROS 토픽을 직접 발행하는 것은 책임 분리 원칙 위반.
  - **태블릿**: 눈높이에서 사용 → UX 문제 해소. 같은 네트워크의 브라우저면 되므로 별도 HW 불필요.
  - **wego_dispatcher polling 방식**: 태블릿이 FastAPI에 HTTP POST → missions 테이블 PENDING 삽입 → wego_dispatcher가 0.5초 폴링으로 수락. 브라우저와 ROS 사이에 FastAPI가 버퍼 역할 → 네트워크 단절에도 안전.
  - **임무 할당 규칙**: limo1 우선, 둘 다 IDLE이면 limo1, 둘 다 BUSY면 503 반환.
  - **포트폴리오 가치**: "브라우저가 아닌 ROS 노드가 로봇을 제어한다"는 설계 원칙을 면접에서 설명 가능.
- **면접 어필**: "rosbridge 방식은 로봇 제어 로직이 브라우저에 있는 설계 결함. 태블릿은 UI만 담당하고, 임무 할당과 ROS 토픽 발행은 wego_dispatcher(rclpy 노드)가 전담하도록 책임을 분리했습니다."
- **Date**: 2026-05-13

---

### DEC-026: UI 기술 스택 선택 — PyQt(관제) / React(방문자/예약)
- **Context**: 3개의 UI가 필요. 각 UI의 핵심 요구사항이 달라 기술 스택을 별도로 결정.
- **Decision**:
  | UI | 스택 | 실행 위치 |
  |----|------|-----------|
  | 관제 GUI | PyQt + rclpy | 관제 노트북 (domain 5) |
  | 방문자 UI | React (HTTP only) | 태블릿 브라우저 (DEC-027로 최종 확정) |
  | 웹 예약 UI | React | 관제 노트북 (포트 3001) |
- **Rationale**:
  - **RQt 제외**: 고정 목적 운용 UI에 플러그인 호스트 구조는 불필요한 복잡성. 현업에서도 운용 UI는 PyQt 직접 작성이 표준.
  - **관제 GUI = PyQt**: amcl_pose, robot_status 실시간 ROS 토픽이 핵심. rclpy + QThread 직접 연결이 가장 안정적.
  - **방문자 UI = React (HTTP only)**: DEC-027에서 rosbridge 제거 결정. 태블릿 브라우저에서 FastAPI HTTP만 사용.
  - **웹 예약 UI = React**: 외부(학부모/학생) 접근 필요 → 웹 기반 필수.
- **면접 어필**: "UI 목적(ROS 실시간 vs DB 조회 vs 외부 접근)에 따라 기술 스택을 달리 선택."
- **Date**: 2026-05-12 (DEC-027로 터치 UI 방식 최종 확정: 2026-05-13)

---

### DEC-025: 예약 백엔드 스택 및 서버 위치 — FastAPI + MySQL + SQLAlchemy, 관제 노트북
- **Context**: 예약 시스템 백엔드 기술 스택과 서버 실행 위치 결정. 다중 클라이언트(웹 예약 UI, LIMO 터치 UI 2대, 관제 GUI) 동시 접근이 필요.
- **Decision**: **FastAPI + MySQL + SQLAlchemy ORM, 관제 노트북(192.168.0.115)에서 실행**
- **Rationale**:
  - **FastAPI**: Python 기반으로 ROS2 코드와 언어 통일. 자동 Swagger 문서(/docs). 비동기 지원. SQLite 대비 다중 클라이언트 동시 접근에 안정적.
  - **MySQL vs PostgreSQL**: 국내 기업 표준이 MySQL. 이 규모(상담 예약 수백 건)에서 두 DB의 실질적 차이 없음. MySQL 선택.
  - **SQLAlchemy ORM**: DB 추상화 → MySQL/PostgreSQL 전환 시 .env DATABASE_URL 한 줄만 변경. 쿼리를 Python으로 표현하여 SQL injection 방지.
  - **관제 노트북 선택**: 서버 노트북은 Nav2 × 2, wego_behaviour × 2 등 ROS 연산 부하가 이미 큼. 관제 노트북은 wego_ui, wego_bridge만 실행 → 여유 있음. 예약 서버(FastAPI)는 ROS와 무관하므로 ulsan_ws 외부에 독립 배치.
  - **포트**: FastAPI 8000, MySQL 3306 (로컬). 외부 클라이언트는 http://192.168.0.115:8000 으로 접근.
  - **CORS**: React(3000) → FastAPI(8000) 크로스오리진 요청을 위해 CORSMiddleware allow_origins=["*"] 설정.
- **패키지 위치**: `/home/yechan/Ulsan-X/ulsan_ui/ulsan_reservation/` (ulsan_ws 외부)
- **면접 어필**: "FastAPI + SQLAlchemy 조합은 Python 생태계 표준 스택. ORM 추상화로 DB 교체 비용을 최소화하고, ROS 연산 부하를 고려해 서버 위치를 관제 노트북으로 결정."
- **Date**: 2026-05-12

---

### DEC-024: NLU 방식 변경 — LLM API 폐기, 터치 UI + DB 조회로 대체
- **Context**: 기존 음성 파이프라인에서 발화("1강의실 안내해줘") → LLM API → waypoint 매핑 방식으로 목적지를 결정했으나, 예약 기반 안내 시스템 도입으로 목적지가 DB에서 결정됨.
- **Decision**: **LLM API 기반 NLU 폐기 → 터치 UI + DB 조회로 완전 대체**
  - 방문자가 LIMO 터치 화면에서 이름 + 생년월일 또는 전화번호 끝자리 입력
  - DB 조회 → 오늘 날짜 + 현재 시간대 예약 확인 → 배정 상담실 반환
  - TTS: "{이름}님 {시간}시 상담 예약으로 {상담실}로 안내합니다."
  - Nav2 goal 전달 → 안내 시작
- **Rationale**:
  - 목적지가 예약 DB에서 결정되므로 NLU 불필요
  - LLM API 응답 지연(DEC-004) 문제 원천 해소
  - 음성 인식 오류(발화 인식 실패, 목적지 매핑 오류) 없이 정확한 목적지 안내
  - wego_voice 패키지에서 NLU 모듈 제거, STT/wakeword도 터치 UI 방식에서는 불필요
  - 면접 어필: "음성 NLU의 불확실성을 예약 시스템 도입으로 구조적으로 제거. 목적지 결정을 DB 조회로 확정하여 안내 정확도 100% 보장."
- **Date**: 2026-05-11

---

### DEC-023: 예약 기반 안내 시스템 도입
- **Context**: 기존 설계는 방문자가 현장에서 음성으로 목적지를 말하면 로봇이 안내하는 방식. 학원 상담 예약 서비스와 연동하여 사전 예약자를 정확하게 안내하는 시스템으로 변경.
- **Decision**: **웹 예약 서비스 + LIMO 터치 UI + 공유 DB** 구조 채택
- **예약 서비스 스펙**:
  - 예약 기간: 당일 ~ 최대 2주 이내, 평일 09:00~17:00, 1시간 단위
  - 예약 정보: 이름 + 전화번호
  - 상담실 4개(counseling_1~2, intensive_counseling_1~2) → 동일 시간대 최대 4명 예약 가능
  - 상담실 자동 배정 (예약자가 선택 불필요)
  - 중복 예약 방지 (4개 상담실 모두 차면 해당 시간대 예약 불가)
- **예약 DB 상태 관리**:
  - `PENDING`: 예약됨, 미방문
  - `IN_PROGRESS`: LIMO 안내 시작 시 전환
  - `COMPLETED`: LIMO 홈 복귀 시 전환
  - 안내 시작 시 즉시 IN_PROGRESS로 업데이트 → 중복 체크인 방지
- **LIMO 터치 UI 흐름**:
  1. 방문자가 홈에 있는 LIMO 터치 화면에서 예약 서비스 선택
  2. 이름 + 생년월일 또는 전화번호 끝자리 입력
  3. DB 조회 → 오늘 날짜 + 현재 시간대 예약 확인
  4. TTS: "{이름}님 {시간}시 상담 예약으로 {상담실}로 안내합니다."
  5. Nav2 goal 전달 → 안내 시작 → DB IN_PROGRESS
- **임무 할당**: 별도 로직 불필요. 안내 중인 LIMO는 물리적으로 홈에 없으므로 방문자가 자연스럽게 홈에 있는 LIMO 사용
- **미결정**:
  - 워크인 방문자(예약 없이 방문) 처리 방식
  - 웹 서비스 호스팅 위치
- **확정**:
  - DB: **MySQL (서버 노트북 로컬)** — 2026-05-12
    - 다중 클라이언트(웹 + LIMO 2대) 동시 접근을 고려해 SQLite 대신 MySQL 선택
    - FastAPI + SQLAlchemy + MySQL 조합 (실무 표준 스택)
    - 서버 노트북에서 MySQL 서버 프로세스 실행 (`sudo apt install mysql-server`)
- **Rationale**:
  - 목적지 결정의 불확실성 제거 (음성 → DB 조회로 확정)
  - 학원 상담 예약이라는 실제 서비스 시나리오와 일치
  - 면접 어필: "실제 서비스 요구사항(예약 시스템)과 로봇 안내를 통합한 end-to-end 시스템 설계."
- **Date**: 2026-05-11

---

### DEC-022: 멀티로봇 충돌 회피 방식 — 우선순위 기반 FSM pause/resume
- **Context**: 기존 `ulsan_obstacle_layer`(PeerObstacleLayer)는 상대 amcl_pose를 global costmap에 LETHAL 장애물로 주입하는 방식. global costmap은 planner가 경로 계획 시에만 참고하므로, 경로 계획 후 이동 중 상대 로봇이 움직여도 controller는 이를 인식하지 못해 실질적 충돌 회피 불가.
- **문제 분석**:
  - global costmap 반영 주기 + planner 재계획 지연 → 충돌 직전에도 반응 불가
  - "경로는 피해서 계획했으나 실행 중에 만나면 충돌"하는 구조적 한계
  - local costmap에 반영해도 Wi-Fi 지연으로 amcl_pose 업데이트가 느려 실시간 회피 불충분
- **Decision**: **우선순위 기반 FSM pause/resume**
  - GUIDING 상태가 RETURNING 상태보다 높은 우선순위
  - 두 로봇이 일정 거리 이내 진입 시 낮은 우선순위 로봇이 Nav2 goal cancel → WAITING 상태 진입
  - 높은 우선순위 로봇이 통과(거리 벌어짐) 후 WAITING 로봇이 goal 재제출 → 주행 재개
- **우선순위 규칙**:
  | LIMO 1 | LIMO 2 | 정지 대상 |
  |--------|--------|-----------|
  | GUIDING | RETURNING | LIMO 2 |
  | RETURNING | GUIDING | LIMO 1 |
  | RETURNING | RETURNING | LIMO 2 (LIMO 1 기본 우선순위) |
- **구현 위치**: `wego_traffic` (중간 노트북)
  - 두 amcl_pose 구독 → 거리 계산 → threshold 이하 시 우선순위 판정
  - `/limo_N/pause`, `/limo_N/resume` 토픽 발행
  - `wego_behaviour` FSM에 `WAITING` 상태 추가: pause 수신 → goal cancel, resume 수신 → goal 재제출
- **Rationale**:
  - 한 로봇이 물리적으로 멈추므로 충돌이 구조적으로 불가능
  - 네트워크 지연 영향 최소화: pause/resume은 단순 토픽 신호로 충분
  - Nav2 lifecycle manager pause는 AMCL까지 멈추는 부작용 → FSM goal cancel 방식 채택
  - 기존 `ulsan_obstacle_layer` (PeerObstacleLayer) 폐기
  - 면접 어필: "동적 장애물에 대한 costmap 기반 회피의 한계를 실기기에서 확인하고, 상태 기반 우선순위 제어로 전환. 충돌 회피를 확률적 회피가 아닌 결정론적 방식으로 보장."
- **Date**: 2026-05-11

---

### DEC-021: 연산 오프로딩 아키텍처 — LIMO 드라이버 전용, 중간 노트북이 Nav2/상위 로직 담당
- **Context**: Jetson Orin Nano의 부하가 과중하여 Nav2 주행 중 control loop missed 경고 및 주행 불안정 발생. LIMO에서 Nav2, AMCL, behaviour, aruco, voice를 모두 실행하는 현재 구조에서는 실용적 운용 불가.
- **Decision**: **LIMO는 하드웨어 드라이버만, 중간 노트북이 모든 연산 담당**
  - LIMO: `limo_base`, `ydlidar`, `orbbec`, `robot_state_publisher`, EKF
  - 중간 노트북: Nav2(AMCL + planner + controller), `wego_behaviour`, `wego_aruco`, `wego_voice`, `wego_traffic`
  - 관제 UI 노트북: `wego_ui`
- **Domain 재할당**:
  | 기기 | 도메인 |
  |------|--------|
  | LIMO 1 | 5 |
  | LIMO 2 | 6 |
  | 중간 노트북 | 5 + 6 (터미널 분리) |
  | 관제 UI 노트북 | 7 |
  - 중간 노트북은 별도 domain 불필요: 터미널마다 `ROS_DOMAIN_ID=5` / `ROS_DOMAIN_ID=6` 설정으로 각 LIMO domain에 직접 참여
  - LIMO와 중간 노트북이 같은 domain → domain bridge 없이 `/scan`, `/odom`, `/tf` 공유
  - 관제 UI 노트북(domain 7)은 기존 wego_bridge로 amcl_pose 수신
- **Rationale**:
  - LIMO는 드라이버만 실행 → CPU/GPU 부하 최소화, 주행 안정성 확보
  - 중간 노트북의 강력한 CPU로 Nav2, STT, NLU 등 연산 집약적 작업 처리
  - 같은 domain에서 DDS로 토픽 자동 공유 → 추가 브릿지 불필요
  - cmd_vel은 중간 노트북 controller_server → LIMO로 직접 전달 (같은 domain)
  - 면접 어필: "Jetson 부하 문제를 실기기에서 확인하고, ROS2 DDS domain 공유 특성을 활용해 별도 브릿지 없이 연산을 노트북으로 오프로딩하는 아키텍처를 설계."
- **기존 구조 대비 변경점**:
  - 기존: 노트북=5, LIMO1=6, LIMO2=7 → 신규: LIMO1=5, LIMO2=6, 중간 노트북=5+6, UI 노트북=7
  - wego_bridge: LIMO에서 실행 → 중간 노트북에서 실행 (amcl_pose를 domain 5,6 → domain 7 브릿징)
  - ulsan_obstacle_layer: 폐기 (DEC-022로 대체)
- **Date**: 2026-05-11

---

### DEC-020: 복도 AMCL drift 해결 방식 — passive ArUco pose corrector
- **Context**: 복도 주행 중 AMCL이 y 방향으로 ~0.29m drift 발생. Nav2 goal checker는 TF(`map→base_link`) 기반 판정 = AMCL 추정값 기반이므로, drift된 상태에서 실제 홈에 도착하기 전에 goal 판정이 내려지는 문제 발생. 복도(긴 직선, 특징점 없음)에서 AMCL symmetric ambiguity로 위치가 당겨지는 현상.
- **문제 분석**:
  - y좌표 모니터링 결과: 복도 진행 중 0.292m 오추정 → goal 판정 → 제자리 회전 후 AMCL 재수렴(0.52). 실제 홈 도착 전에 멈추는 패턴 반복.
  - 복도 벽 마커: 로봇이 복도를 가로질러 홈 방향으로 이동하므로 카메라가 벽을 바라보지 않아 감지 불가.
  - visual servoing: 홈 도착 후 1회 보정에는 적합하나 주행 중 drift 누적을 막지 못함.
- **Options**:
  - A) Nav2 time-based goal checker (일정 시간 머물러야 판정) — Nav2 플러그인 커스텀 필요, 복잡
  - B) goal tolerance 완화 → 이미 0.10m, 더 완화하면 반대로 정밀도 저하
  - C) update_min_d/a 낮춰 AMCL 업데이트 빈도 증가 → 부분 완화
  - D) **passive ArUco pose corrector** — 바닥 마커를 웨이포인트마다 설치, 주행 중 감지 시 /initialpose 자동 발행
- **Decision**: **C + D 병행**
  - `update_min_d: 0.25→0.1`, `update_min_a: 0.2→0.1` (즉시 적용)
  - `aruco_pose_corrector` 노드: 주행 중 바닥/벽 마커 감지 → full 3D transform → /initialpose 발행
- **Rationale**:
  - 바닥 마커(카메라 하향 약 15°, 높이 20cm → 75cm 앞 바닥 인식): 로봇 진행 방향 앞에 두면 이동 경로에서 반드시 감지됨.
  - TF lookup(`base_link←camera_optical`)으로 camera tilt 자동 반영 → 마커 위치 부정확한 수동 계산 불필요.
  - MIN_CONSISTENT=3, COOLDOWN=10s: 단일 프레임 노이즈 방지 + 과도한 AMCL 리셋 방지.
  - 변환 체인: `T_map_base = T_map_marker × inv(T_cam_marker) × inv(T_base_cam)` (full 3D, 카메라 tilt 반영)
  - 면접 어필: "AMCL만으로 해결 불가한 복도 drift를 마커 절대 좌표로 주기적 리셋하는 구조. 상용 AGV의 QR 바닥 마커 체크포인트와 동일한 원리."
- **구현 현황 (2026-05-07)**:
  - `wego_aruco/pose_corrector.py` 신규 작성 (aruco_pose_corrector 노드)
  - `setup.py` entry point 추가
  - markers.yaml 확장: map 좌표 미측정(map_x=0, map_y=0)이면 자동 건너뜀
- **실기기 검증 완료 (2026-05-08)**:
  - home1 바닥 마커(ID 0) 방향 캘리브레이션: 시계방향 90° 회전으로 map_yaw=π/2 확정
  - classroom_1 → home1 왕복 주행 중 AMCL 자동 보정 확인 (10s cooldown 간격)
  - Nav2 home1 goal 성공 확인
- **Date**: 2026-05-07 → 2026-05-08 검증 완료

---

### DEC-019: SLAM 알고리즘 선택 — Cartographer (SLAM Toolbox 제외)
- **Context**: 학원 복도(긴 직선 + 유리 환경)에서 SLAM 맵 빌딩 필요. ROS2 표준인 SLAM Toolbox를 먼저 시도했으나 맵 빌딩 실패 반복.
- **문제 분석**:
  - SLAM Toolbox(karto 백엔드)는 스캔-스캔 매칭 방식 → 복도처럼 양쪽 벽 패턴이 동일한 환경에서 현재 스캔을 이전 위치의 스캔으로 오인 (Symmetric Ambiguity)
  - 결과: 로봇이 전진해도 TF가 계속 당겨져 맵에서 제자리걸음 현상 발생
  - 추가 문제: YDLiDAR Tmini Plus의 드라이버가 매 스캔 포인트 수를 250↔251로 흔들림 → SLAM Toolbox karto가 첫 스캔 기준 포인트 수와 다른 스캔을 전부 reject → 맵 업데이트 없음
- **Decision**: **Cartographer로 SLAM 전환**
  - SLAM: Cartographer → `.pgm` + `.yaml` 맵 저장
  - 위치추정: AMCL (Cartographer 맵 호환)
  - 주행: Nav2
- **Rationale**:
  - Cartographer는 서브맵(submap) 단위로 스캔을 누적 후 매칭 → 단일 스캔 오매칭에 강함
  - CSM(Correlative Scan Matcher) + Ceres 최적화로 복도 환경에서 더 안정적
  - 스캔 포인트 수 변동에 관대 (karto처럼 reject 없음)
  - 유리 환경에서의 난반사 강건성은 두 알고리즘 동일 (센서 레벨 문제)
  - Cartographer 맵(.pgm)은 AMCL과 완전 호환 → 기존 Nav2 스택 재사용 가능
- **트레이드오프**:
  - SLAM Toolbox localization 모드(posegraph 기반) 사용 불가 → AMCL로 대체
  - Cartographer는 SLAM Toolbox보다 무거움 (실시간 주행 중 CPU 부하 높음)
- **면접 어필**: "복도 환경의 Symmetric Ambiguity 문제를 실험적으로 확인하고, 서브맵 기반 CSM을 사용하는 Cartographer로 전환했습니다. 스캔-스캔 매칭 방식의 한계를 직접 경험하고 알고리즘 특성을 비교 분석하여 선택했습니다."
- **Date**: 2026-05-05

---

### DEC-018: ArUco 홈 도킹 방식 — 2-Phase Lateral-Only Visual Servoing + AMCL 리셋
- **Context**: 홈 복귀 시 ArUco 마커 활용 방식을 결정. 초기 설계는 /initialpose 발행(AMCL 교정)만 수행하는 방식이었으나, visual servoing(물리 정밀 정차)으로 전환 논의 후 두 방식을 결합하는 방향으로 최종 확정. 이후 실기기 검증 과정에서 2-Phase 설계로 구체화.
- **Decision**: **Coarse-to-Fine 패턴** — Nav2 대략 이동 → 2-Phase ArUco visual servoing → 마커 역산 /initialpose 발행
  - Phase 1: 전진 접근 (2m → 30cm) + lateral-only 보정
  - Phase 2: 후진 정밀 정차 (30cm → 2.007m) + lateral-only 보정
- **Rationale**:
  - visual servoing만: 물리 위치는 정밀하나 AMCL drift 미보정 → 다음 안내에서 오차 누적
  - /initialpose만: AMCL 보정되나 물리 위치는 Nav2 허용 오차(±10~30cm) 그대로
  - 두 방식 결합: 물리 정밀 정차 + AMCL 리셋 동시 달성
  - MiR, Fetch 등 상용 AMR 및 Nav2 opennav_docking과 동일한 산업 표준 패턴
  - **2-Phase 설계 이유**: 단순 전진 접근(dist→target_dist)은 30cm에서 lateral 미수렴으로 타임아웃 발생. 30cm까지 전진 정렬 후 후진하면 Phase 1의 정밀 정렬이 Phase 2 시작점으로 활용됨.
  - **lateral-only 제어 이유**: 제자리 yaw 보정 시 로봇 회전으로 마커가 카메라 FOV 이탈 → 미감지. lateral만 보정해도 전진 중 기하학적으로 yaw가 수렴함.
  - 면접 어필: "Coarse-to-Fine Localization 패턴을 적용했으며, 정밀 정차 후 알려진 절대 좌표로 AMCL을 리셋하는 방식은 상용 AMR과 동일한 구조. 카메라 FOV 유지를 위한 lateral-only 제어는 실기기 반복 검증을 통해 도출."
- **구현 현황 (2026-05-04)**:
  - `wego_aruco/aruco_localizer.py`: 2-Phase 구조, lateral-only P제어, /aruco_correct 서비스
  - `wego_behaviour/states.py` ReturningState: /aruco_correct 호출만 수행
  - /initialpose 발행 주체: `wego_aruco` (마커 map 좌표 역산)
    - 역산 공식: `robot_x = marker_x + total_dist × cos(marker_yaw)` (**+ 부호**)
    - cam_offset: 0.23m (base_link → camera_link)
  - 실기기 검증 결과: Phase 1 lat=0.001m, Phase 2 lat=0.008m 수렴
- **마커 구성**: ID 0 (LIMO1), ID 1 (LIMO2) — 각 로봇 홈 정면 벽 부착, 크기 20cm × 20cm
- **markers.yaml 현황 (2026-05-08 업데이트)**:
  - ID 0: target_dist=0.946, map_x=0.0, map_y=-0.196, map_yaw=1.5708, calibrated=true
    - home_robot1 (0.0, 0.98, -π/2) 기준 역산: camera_y=0.75, marker_y=0.75-0.946=-0.196
    - 마커 방향: 시계방향 90° 회전으로 map_yaw=π/2 확정 (캘리브레이션)
  - ID 1: 미측정.
- **미완료**: _publish_initialpose 부호 버그 수정 + /initialpose 주석 해제, markers.yaml ID 1 측정
- **Date**: 2026-05-01 → 2026-05-04 → 2026-05-08 업데이트

---

### ~~DEC-017: wego_voice on_duty 게이팅 위치~~ — **폐기 (2026-05-11)**
- **폐기 이유**: DEC-024로 wakeword/STT/NLU가 제거되고 터치 UI + DB 조회 방식으로 전환됨. on_duty 개념 자체가 불필요해져 게이팅 로직도 함께 폐기.
- **Date**: 2026-04-30 → 폐기 2026-05-11

---

### DEC-016: 유리 구간 주행 불안정 해결 방식 + ArUco 마커 운용 전략 ✅
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
  - **Keepout Filter (금지구역) + DenoiseLayer 적용** → 목적지·홈 구간 주행 정상화. 유리 회전문 통과는 여전히 불가.
- **최종 결론 (2026-04-29 실기기 검증)**:
  - Keepout Filter는 global costmap에만 적용 → global 경로는 우회. 그러나 유리 근처를 지나는 경로에서 local costmap phantom으로 인해 `controller_server: Failed to make progress` 발생.
  - **유리 회전문 통과는 LiDAR 물리 한계 — 소프트웨어로 완전 해결 불가** 확정
  - **운용 정책: 유리 회전문 통과 구간은 경로에서 영구 제외**
  - 목적지·홈 안내 주행에는 유리 회전문 통과가 불필요 → 서비스 요구사항 내에서 완전 동작
  - 면접 어필: "LiDAR 물리적 한계를 실기기 검증으로 확인하고, 운용 요구사항 내에서 완전 동작하는 현실적 판단을 내렸다"
- **ArUco 마커 용도 재정의 (DEC-016 핵심 결정, 2026-04-30 최종 확정)**:
  - 유리 구간 보정 목적 → **폐기**
  - 각 목적지 마커 부착 방식 → **폐기** (Nav2 정밀도로 목적지 도착은 충분)
  - **홈 복귀 시 1회 보정**으로 최종 확정: 로봇이 목적지 안내 후 홈으로 복귀할 때 ArUco로 정밀 정차
  - 마커는 **홈 위치에만 2개** (로봇1 홈, 로봇2 홈 — 각 로봇이 자신의 마커만 탐색)
  - drift 리셋 타이밍: 홈 복귀 시 1회로 충분 (편도 주행 누적 오차 리셋)
  - 산업용 AMR 도킹 마커와 동일 원리
  - 면접 어필: "목적지는 Nav2 정밀도로 충분하고, 장시간 운영 시 누적되는 AMCL drift는 홈 복귀 시 ArUco 1회 보정으로 리셋하는 구조를 설계했다. 마커 수를 최소화(2개)하면서 정밀도를 보장하는 현실적 설계."
- **마커 사양**: ArUco DICT_4X4_50, 10cm × 10cm, 종이 인쇄, 각 로봇 홈 위치 벽 부착
- **구현 패키지**: `wego_aruco` (신규, ament_python) — 상세 설계는 `docs/ref/ARUCO-LOCALIZER.md`
- **Date**: 2026-04-28 (재확정: 2026-04-29, 최종 결론: 2026-04-30)

---

### ~~DEC-015: 멀티로봇 임무 할당 — on_duty 코디네이터~~ — **폐기 (2026-05-11)**
- **폐기 이유**: DEC-023으로 터치 UI 방식 도입. 방문자가 물리적으로 홈에 있는 LIMO를 직접 선택하므로 on_duty 개념이 불필요. 안내 중인 LIMO는 홈에 없어 자연스럽게 분리됨.
- **wego_traffic 역할 재정의**: on_duty 결정 제거 → **충돌 회피(pause/resume)만 담당** (DEC-022)
- **Date**: 2026-04-27 → 폐기 2026-05-11

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
  - ~~`VoiceTriggerCondition`~~: **폐기** — 웨이크워드 제거(DEC-024)로 불필요
  - ~~`PeerRobotBusyCondition`~~: **폐기** — on_duty 개념 제거(DEC-015 폐기)로 불필요
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
