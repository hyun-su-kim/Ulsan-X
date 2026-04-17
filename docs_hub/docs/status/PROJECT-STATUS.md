# AI 기반 학원 안내 로봇 — Project Status

## Current Phase
**환경 구성 진행 중**
멀티로봇 TF 프레임 분리 전 구간 구현 완료 (teleop ~ Nav2 ~ Domain Bridge ~ 노트북 RViz).
다음 단계: cyclonedds_peers.xml IP 입력 → 실기기 통신 검증 → SLAM 지도 작성.

---

## Active Tracks

| 트랙 | 상태 | 담당 패키지 |
|------|------|------------|
| 시스템 아키텍처 설계 | in progress | — |
| 통신 환경 구성 (CycloneDDS + Domain Bridge) | **구현 완료, 검증 대기** | wego_fleet |
| SLAM 지도 작성 | planned | wego (cartographer) |
| Nav2 경로 계획 & AMCL | planned | wego_2d_nav |
| Fleet 충돌 회피 (가상 장애물) | planned | wego_fleet |
| 음성 파이프라인 (VAD→Wake→STT→NLU→TTS) | planned | wego_voice (신규) |
| 행동 트리 최상단 관리 | planned | wego_behaviour (신규) |
| 관제 UI | not started | — |

---

## Execution Checklist

### P0 — 환경 기반 구축 (Immediate)
- [x] CycloneDDS 설치 및 `cyclonedds_peers.xml` 유니캐스트 설정 — done (2026-04-16), TS-001 참고
- [x] DOMAIN_ID 확정 — done (2026-04-16): 노트북=5, LIMO 1=6, LIMO 2=7
- [x] 멀티로봇 TF frame 분리 — done (2026-04-17): DEC-005, DEC-006, DEC-008 참고
  - `diff_navigation_params.yaml`: AMCL/Nav2 ROBOT_NAME 플레이스홀더 (기존)
  - `navigation_diff_launch.py`: robot_name 인자 + Python 치환 방식 (기존)
  - `teleop_launch.py`: robot_name 인자 추가, robot_state_publisher frame_prefix, EKF 템플릿 치환 (신규)
  - `limo_ekf_robot.yaml`: EKF odom_frame/base_link_frame ROBOT_NAME 템플릿 (신규)
- [x] Domain Bridge 설정 파일 작성 — done (2026-04-17): wego_fleet 패키지
  - `domain_bridge_robot1.yaml`: /tf,/map → domain5, /amcl_pose → domain7
  - `domain_bridge_robot2.yaml`: /tf → domain5, /amcl_pose → domain6
  - `laptop_bridge_launch.py`: 노트북 실행 런치
  - `fleet_monitor.rviz`: 두 로봇 위치 + 지도 표시
- [x] cyclonedds_peers.xml 실제 IP 입력 — done (2026-04-17): 192.168.0.115, 192.168.0.116
- [x] camera TF frame prefix 적용 — done (2026-04-17)
  - `camera_tilt_launch.py`: robot_name 인자 추가, 모든 카메라 프레임에 prefix 적용
  - `teleop_launch.py`: Orbbec `camera_name=robot_name+'_camera'` → `robot1_camera_link` 연결
- [x] Domain Bridge 설계 확정 — done (2026-04-17): DEC-010
  - `robot_bridge_launch.py`: 각 LIMO에서 실행, ROS_DOMAIN_ID 자동 읽음
  - `domain_bridge_robot.yaml`: 단일 템플릿, leader 인자로 /map 전송 여부 결정
- [ ] 실기기 Domain Bridge 통신 검증 (테스트 예정)
  - LIMO 1: `ros2 launch wego_fleet robot_bridge_launch.py leader:=true`
  - 노트북: `ros2 run rviz2 rviz2` → map 위에 robot1 TF 확인
- [ ] Cartographer SLAM으로 학원 지도 작성 (LIMO 1 기준)
- [ ] 저장된 맵을 LIMO 2에 복사
- [ ] 노트북 RViz에서 두 로봇 위치 확인

### P1 — 핵심 기능 구현 (Core)
- [ ] `wego_fleet` 패키지: `/amcl_pose` 수신 → 원형 가상 장애물 costmap 주입 (FleetObstacleLayer C++ 플러그인)
- [ ] `waypoints.yaml` 작성: 강의실, 상담실, 회의실 등 목적지 좌표 정의
- [ ] Nav2 BT 목적지 연동 (waypoint → navigate_to_pose action)
- [ ] `wego_behaviour` 패키지: 최상단 BT 설계 (대기 → 호출 → 안내 → 복귀)
- [ ] 우선순위 기반 임무 할당: 리더 busy → 서브 활성화 로직
- [ ] 음성 파이프라인 Level 1~3 구현 (VAD + openWakeWord + faster-whisper CUDA)
- [ ] 음성 파이프라인 Level 4~6 구현 (NLU if-else + Gemini API + Piper TTS)
- [ ] YOLO 사람 감지 → 방향 회전 + 10~20s 안내 멘트 발화

### P2 — 고도화 (Enhancement)
- [ ] NLU 백업: Gemma-2B (Ollama) 네트워크 단절 시 로컬 폴백
- [ ] 목적지 도달 후 "추가 용무 확인" 대화 흐름
- [ ] 관제 UI (기술 구현 완료 후 착수)
- [ ] 전력 최적화: 대기 상태 CPU/GPU 사용량 프로파일링
- [ ] 다국어 안내 검토 (영어권 방문자 대응)

---

## 알려진 이슈 / 리스크

| 이슈 | 심각도 | 상태 |
|------|--------|------|
| Orin Nano GPU 메모리: YOLO + faster-whisper 동시 가동 시 OOM 가능성 | High | 검토 필요 |
| openWakeWord "헤이 리모" 커스텀 모델 학습 필요 여부 | Medium | 미결정 |
| 두 로봇이 동시에 호출될 때 충돌 시나리오 | Medium | BT 설계 시 처리 예정 |
| Gemini API 응답 지연이 대화 흐름에 미치는 영향 | Low | 모니터링 |
