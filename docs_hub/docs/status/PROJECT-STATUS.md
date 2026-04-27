# AI 기반 학원 안내 로봇 — Project Status

## Current Phase
**SLAM 지도 작성 준비 중**
Domain Bridge 실기기 통신 검증 완료 (2026-04-22). Cartographer + AMCL 파라미터 튜닝 정리 완료 (2026-04-27).
다음 단계: 실기기 SLAM 지도 작성 → 맵 후보정 → 배포.

---

## Active Tracks

| 트랙 | 상태 | 담당 패키지 |
|------|------|------------|
| 시스템 아키텍처 설계 | **완료** | — |
| 통신 환경 구성 (CycloneDDS + Domain Bridge) | **완료** | wego_bridge |
| SLAM 지도 작성 | in progress | wego (cartographer) |
| Nav2 경로 계획 & AMCL | planned | wego_2d_nav |
| Fleet 충돌 회피 (PeerObstacleLayer) | planned | ulsan_obstacle_layer |
| 행동 트리 최상단 관리 | planned | wego_behaviour (신규) |
| 음성 파이프라인 (VAD→Wake→STT→NLU→TTS) | planned | wego_voice (신규) |
| 관제 UI | planned | wego_ui (신규, 노트북 전용) |

---

## Execution Checklist

### P0 — 환경 기반 구축
- [x] CycloneDDS 설치 및 `cyclonedds_peers.xml` 유니캐스트 설정 — done (2026-04-16), TS-001 참고
- [x] DOMAIN_ID 확정 — done (2026-04-16): 노트북=5, LIMO 1=6, LIMO 2=7
- [x] cyclonedds_peers.xml 실제 IP 입력 — done (2026-04-22): LIMO1=192.168.0.100, LIMO2=192.168.0.101, 노트북1=192.168.0.115, 노트북2=192.168.0.116
- [x] 멀티로봇 통신 설계 확정 — done (2026-04-21): DEC-011, DEC-012
  - **amcl_pose 공유 방식** 채택 (TF frame prefix 방식 폐기)
  - **맵 파일 사전 배포** 방식 채택 (domain bridge로 /map 스트리밍 방식 폐기)
  - 각 기기가 로컬 map_server로 /map 발행, domain bridge는 amcl_pose만 전달
- [x] `wego_bridge` 패키지 구현 완료 — done (2026-04-22): TS-002, TS-003 수정 포함
  - `config/domain_bridge_robot.yaml`: ROBOT_DOMAIN, DEST_DOMAIN, ROBOT_NAME 플레이스홀더 템플릿 (맵 형식)
  - `launch/robot_bridge_launch.py`: OpaqueFunction → bridge 인스턴스 2개 생성 (laptop/peer)
  - 동작: `/amcl_pose` (domain N) → `/limo_1(2)/amcl_pose` (domain 5, domain PEER) 동시 브릿징
- [x] 실기기 Domain Bridge 통신 검증 — done (2026-04-22)
  - LIMO 1(domain 6) → 노트북(domain 5): `/limo_1/amcl_pose` 수신 확인
  - TS-002, TS-003 발생 및 해결 (COMMUNICATION.md 참고)
- [ ] Cartographer 파라미터 수정 (`wego/config/limo_lds_2d.lua`) — 유리+복도 환경 대응 **(SLAM 전에 적용)**
  ```lua
  POSE_GRAPH.optimize_every_n_nodes = 5
  POSE_GRAPH.constraint_builder.min_score = 0.55
  POSE_GRAPH.constraint_builder.global_localization_min_score = 0.55
  POSE_GRAPH.global_sampling_ratio = 0.1
  TRAJECTORY_BUILDER_2D.missing_data_ray_length = 1.0
  TRAJECTORY_BUILDER_2D.submaps.num_range_data = 35
  TRAJECTORY_BUILDER_2D.ceres_scan_matcher.rotation_weight = 100
  TRAJECTORY_BUILDER_2D.num_accumulated_range_data = 2
  ```
- [ ] Cartographer SLAM으로 학원 지도 작성 (LIMO 1 기준)
  - 유리에 종이 부착 → 복도 임시 장애물(화분) 배치 → 천천히 루프 주행
  - RViz `/constraint_list`에서 loop closure 노란선 확인 후 저장
- [ ] 맵 후보정 (GIMP)
  - 화분 흔적 → 흰색(free space)으로 제거
  - 유리 스파이크 노이즈 제거
  - 유리 위치 → 검은 픽셀(가상 벽)으로 처리
- [ ] AMCL 파라미터 수정 (`wego_2d_nav/params/diff_navigation_params.yaml`) — 스캔 불일치 최소화 **(지도 완성 후 적용, 실기기 테스트하며 확정)**
  ```yaml
  do_beamskip: true
  z_hit: 0.4
  z_rand: 0.6
  sigma_hit: 0.35
  max_beams: 120
  min_particles: 1000
  max_particles: 3000
  recovery_alpha_slow: 0.001
  recovery_alpha_fast: 0.1
  ```
- [ ] 맵 파일(`map.pgm`, `map.yaml`) scp로 LIMO 2 및 노트북에 배포
  ```bash
  scp map.pgm map.yaml wego@192.168.0.101:~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/
  scp map.pgm map.yaml user@192.168.0.115:~/maps/
  scp map.pgm map.yaml user@192.168.0.116:~/maps/
  ```
- [ ] 노트북에서 맵 + 두 로봇 위치 마커 확인

### P1 — 핵심 기능 구현 (Core)

#### 자율주행
- [ ] `ulsan_obstacle_layer` 패키지: PeerObstacleLayer 빌드 및 실기기 검증
  - `/limo_1/amcl_pose` 또는 `/limo_2/amcl_pose` 구독 (ROS_DOMAIN_ID로 자동 결정)
  - 상대 로봇 위치 → 원형 가상 장애물 → global costmap LETHAL_OBSTACLE 주입
- [ ] `waypoints.yaml` 작성: 강의실, 상담실, 회의실 등 목적지 좌표 정의

#### 미션 제어 (FSM + Nav2 BT 커스텀)
- [ ] `wego_behaviour` 패키지: **Yasmin FSM** 구현 (대기 / 안내 중 / 복귀 중 상태 전환) — DEC-014
- [ ] Nav2 BT 커스텀 노드 작성: `VoiceTriggerCondition`, `PeerRobotBusyCondition` (C++)
- [ ] Nav2 `navigate_to_pose` 액션 연동 (waypoint → 목적지 이동)
- [ ] 우선순위 기반 임무 할당: 상대 로봇 busy 여부 → 서브 활성화 로직

#### 음성 파이프라인
- [ ] `wego_voice` 패키지: VAD + openWakeWord + faster-whisper (STT) 구현
- [ ] NLU: 발화 키워드 파싱 → `waypoints.yaml` 목적지 매핑
- [ ] TTS (Piper) 구현
- [ ] 음성 파이프라인 → BT 연결 (발화 → navigate_to_pose 호출)

### P2 — 완성도 + 추가 개발
- [ ] 관제 UI (`wego_ui`, 노트북 전용): 지도 + 두 로봇 실시간 위치 마커 시각화
- [ ] 초음파/카메라 → local costmap 연동 (움직이는 유리문 동적 장애물 대응)
- [ ] YOLO 사람 감지 → 방향 회전 + 안내 멘트 발화
- [ ] NLU 백업: Gemma-2B (Ollama) 네트워크 단절 시 로컬 폴백
- [ ] 목적지 도달 후 "추가 용무 확인" 대화 흐름
- [ ] GPU 메모리 프로파일링 (YOLO + faster-whisper 동시 가동 OOM 검증)
- [ ] 다국어 안내 검토 (영어권 방문자 대응)

---

## 알려진 이슈 / 리스크

| 이슈 | 심각도 | 상태 |
|------|--------|------|
| Orin Nano GPU 메모리: YOLO + faster-whisper 동시 가동 시 OOM 가능성 | High | P2에서 프로파일링 예정 |
| openWakeWord "헤이 리모" 커스텀 모델 학습 필요 여부 | Medium | 미결정 |
| 두 로봇이 동시에 호출될 때 충돌 시나리오 | Medium | BT 설계 시 처리 예정 |
| Gemini API 응답 지연이 대화 흐름에 미치는 영향 | Low | 모니터링 |
