# AI 기반 학원 안내 로봇 — Project Status

## Current Phase
**단일 로봇 자율주행 검증 단계**
SLAM 완료 (유리 종이 부착 + 복도 임시 장애물 + 루프 주행 + GIMP 후보정). Nav2 주행 문제 해결 중.

---

## Active Tracks

| 트랙 | 상태 | 담당 패키지 |
|------|------|------------|
| 시스템 아키텍처 설계 | **완료** | — |
| 통신 환경 구성 (CycloneDDS + Domain Bridge) | **완료** | wego_bridge |
| SLAM 지도 작성 | **완료** | wego (cartographer) |
| Nav2 경로 계획 & AMCL | in progress | wego_2d_nav |
| Fleet 충돌 회피 (PeerObstacleLayer) | planned | ulsan_obstacle_layer |
| 행동 트리 최상단 관리 | planned | wego_behaviour (신규) |
| 음성 파이프라인 (VAD→Wake→STT→NLU→TTS) | planned | wego_voice (신규) |
| 관제 UI | planned | wego_ui (신규, 노트북 전용) |

---

## Execution Checklist

### 완료 — 환경 기반 구축
- [x] CycloneDDS 설치 및 `cyclonedds_peers.xml` 유니캐스트 설정 — done (2026-04-16), TS-001 참고
- [x] DOMAIN_ID 확정 — done (2026-04-16): 노트북=5, LIMO 1=6, LIMO 2=7
- [x] cyclonedds_peers.xml 실제 IP 입력 — done (2026-04-22): LIMO1=192.168.0.101, LIMO2=192.168.0.102, 노트북1=192.168.0.115, 노트북2=192.168.0.116
- [x] 멀티로봇 통신 설계 확정 — done (2026-04-21): DEC-011, DEC-012
- [x] `wego_bridge` 패키지 구현 + 실기기 통신 검증 — done (2026-04-22)
- [x] Cartographer SLAM 지도 작성 완료 — done (2026-04-28~29)
  - 유리 구간: 종이 부착으로 LiDAR 특징점 확보 (매핑 후 제거)
  - 복도 drift: 임시 장애물 배치 + 루프 주행(왕복) + `/constraint_list` loop closure 확인
  - 후처리: GIMP 노이즈 제거 + 유리문 구간 가상 벽 처리
- [x] 맵 파일 git 커밋 — 각 기기 `git pull`로 배포

---

### Phase 1 — 단일 LIMO 자율주행 완성 (현재 진행 중)

> LIMO 1대가 학원을 완벽하게 자율주행하는 것이 목표

- [x] `ulsan_obstacle_layer` 빌드 — LIMO ulsan_ws 전체 빌드 완료. `peer_valid_` 플래그로 상대 amcl_pose 수신 전까지 완전 no-op — 단독 주행에 영향 없음.
- [ ] Nav2 전체 스택 실기기 테스트 — AMCL 초기 위치 설정(RViz 2D Pose Estimate) 후 동작 확인
- [ ] AMCL 파라미터 튜닝 (`diff_navigation_params.yaml`) — 실기기 주행하며 확정
- [ ] **유리 구간 유령 장애물 해결** — LiDAR 난반사 → global costmap 오염 → 빙글빙글 (DEC-016)
  - 다수 소프트웨어 방법 시도 후 폐기 (obstacle_max_range·observation_persistence·laser_filters 등)
  - **확정: Keepout Filter (금지구역) + DenoiseLayer** — 구현 예정
  - 유리문은 운용 중 항상 열린 상태로 가정
- [ ] **ArUco 마커 기반 목적지 정차 보정** — 장시간 운영 시 누적 오차 리셋 (DEC-016)
  - 강의실, 상담실 등 각 목적지 벽에 마커 부착 (10cm × 10cm, DICT_4X4_50)
  - 도착 시 마커 감지 → `/initialpose` 보정 → 정확한 정차 위치 보장
  - 구현 계획: `docs/ref/ARUCO-LOCALIZER.md` 참고
- [ ] `waypoints.yaml` 작성 — 강의실, 상담실, 회의실 등 목적지 좌표 (Nav2로 실제 주행하며 기록)

---

### Phase 2 — 2대 Fleet 구성

> LIMO 2대가 서로를 인식하고 회피하며 독립적으로 주행

- [ ] `ulsan_obstacle_layer` 실기기 검증 — 2대 동시 운행 시 상대 amcl_pose → global costmap LETHAL_OBSTACLE 반영 확인
- [ ] `wego_bridge` 실운용 — 두 로봇 amcl_pose 노트북(domain 5) 수신 확인
- [ ] `wego_ui` 관제 GUI — 노트북에서 지도 + 두 로봇 실시간 위치 마커 시각화

---

### Phase 3 — 핵심 기능 구현

#### 미션 제어
- [ ] `wego_behaviour` 패키지: **Yasmin FSM** 구현 (대기 / 안내 중 / 복귀 중) — DEC-014
- [ ] Nav2 BT 커스텀 노드: `VoiceTriggerCondition`, `PeerRobotBusyCondition` (C++)
- [ ] 중앙 코디네이터 (노트북): robot_status 구독 → on_duty 결정 — DEC-015
- [ ] Nav2 `navigate_to_pose` 액션 연동

#### 음성 파이프라인
- [ ] `wego_voice` 패키지: VAD + openWakeWord + faster-whisper (STT)
- [ ] NLU: 발화 키워드 → `waypoints.yaml` 목적지 매핑
- [ ] TTS (Piper)
- [ ] 음성 파이프라인 → FSM 연결

---

### Phase 4 — 완성도
- [ ] 초음파 센서 → local costmap range_sensor_layer 연동 (유리문 닫힘 감지 + 음성 대기) — 유리문 닫힘 시 경로 생성 불가 → TTS "유리문을 열어주세요" + WAIT 상태
- [ ] YOLO 사람 감지 → 방향 회전 + 안내 멘트
- [ ] NLU 백업: Gemma-2B (Ollama) 로컬 폴백
- [ ] 목적지 도달 후 "추가 용무 확인" 대화 흐름
- [ ] GPU 메모리 프로파일링 (YOLO + faster-whisper 동시 가동)
- [ ] 다국어 안내 검토

---

## Nav2 단독 주행 현황 (2026-04-29 기준)

### 정상 동작
- 복도·강의실 등 일반 구간 자율주행 정상
- AMCL 위치추정 정상 (RViz `/particlecloud` 파티클 수렴 확인)

### 미해결 문제

| 문제 | 원인 | 해결 방향 | 상태 |
|------|------|----------|------|
| 유리 회전문 구간 빙글빙글 / 통과 불가 | LiDAR 난반사 → global costmap phantom obstacle | Keepout Filter + DenoiseLayer | **구현 예정** |
| `waypoints.yaml` 미작성 | 실기기 주행하며 RViz로 좌표 기록 필요 | Nav2 주행 안정화 후 진행 | 미착수 |
| AMCL 파라미터 미최적화 | 위치추정은 되나 장시간 운영 시 drift 가능성 | 실기기 장시간 주행하며 확정 | 진행 중 |

### phantom obstacle 해결 시도 이력

| 시도 방법 | 결과 |
|----------|------|
| `obstacle_max_range` 축소 | phantom이 2m 이내 → 범위 축소로 효과 없음 |
| `observation_persistence` 단축 | 매 스캔 동일 위치 재생성 → 효과 없음 |
| `laser_filters` 각도 필터 | 회전 중 유리 방향 계속 변화 → 완벽 해결 불가 |
| 맵 유리 구간 연장 (GIMP) | 로봇 통과 경로 차단 → 포기 |
| Keepout Filter (센서 무시 구역) | phantom이 폴리곤 밖에도 생성 → 효과 없음 |
| `clearing` / `combination_method` 조정 | 근본 해결 안 됨 |
| VoxelLayer + Orbbec 카메라 검토 | IR 카메라도 유리 투과 → depth 값 없음 → 부적합 |

> 상세 엔지니어링 판단 기록: `docs/ref/NAVIGATION.md` — "Nav2 주행 문제 해결 과정" 섹션

---

## 알려진 이슈 / 리스크

| 이슈 | 심각도 | 상태 |
|------|--------|------|
| Orin Nano GPU 메모리: YOLO + faster-whisper 동시 가동 시 OOM 가능성 | High | P2에서 프로파일링 예정 |
| openWakeWord "헤이 리모" 커스텀 모델 학습 필요 여부 | Medium | 미결정 |
| 두 로봇이 동시에 호출될 때 충돌 시나리오 | Medium | BT 설계 시 처리 예정 |
| Gemini API 응답 지연이 대화 흐름에 미치는 영향 | Low | 모니터링 |
