# ARCHITECTURE — AI 기반 학원 안내 로봇

## 시스템 개요

```
[ 학원 입구 ]
  ┌──────────────────────┐       ┌──────────────────────┐
  │     리더 로봇         │       │     서브 로봇          │
  │     (Robot 1)        │       │     (Robot 2)         │
  │   DOMAIN_ID=6        │       │   DOMAIN_ID=7         │
  │                      │       │                       │
  │  /amcl_pose ─────────┼──────►│ FleetObstacleLayer    │
  │  FleetObstacleLayer ◄├───────┼─ /amcl_pose           │
  └──────────┬───────────┘       └──────────┬────────────┘
             │ /amcl_pose                   │ /amcl_pose
             │ /map (리더만)                │
             └──────────────┬───────────────┘
                            │ (domain bridge → domain 5)
                  ┌─────────▼──────────┐
                  │   서버 노트북       │
                  │   DOMAIN_ID=5      │
                  │   관제 UI          │
                  │  - 두 로봇 위치 표시│
                  │  - 맵 표시         │
                  └────────────────────┘
```

**통신 흐름 요약:**
- 각 로봇 → domain 5(노트북): `/amcl_pose` → 관제 UI 위치 마커 표시
- Robot1 → domain 7(Robot2): `/amcl_pose` → Robot2 FleetObstacleLayer 입력
- Robot2 → domain 6(Robot1): `/amcl_pose` → Robot1 FleetObstacleLayer 입력
- `/map`: **domain bridge 없음**. 각 기기(LIMO 1, LIMO 2, 노트북)가 로컬 map_server로 독립 발행

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

**운용 원칙 (DEC-015)**: 노트북 `wego_coordinator`가 두 로봇 상태를 보고 on_duty 로봇을 결정. LIMO1 IDLE이면 LIMO1 on_duty, LIMO1 BUSY이면 LIMO2 on_duty. 둘 다 BUSY이면 대기.

---

## 하드웨어 구성

| 항목 | 사양 |
|------|------|
| 로봇 플랫폼 | Wego (2대) |
| 온보드 컴퓨터 | NVIDIA Jetson Orin Nano |
| GPU | 내장 GPU (CUDA) — faster-whisper, YOLO 가속 |
| LiDAR | (wego 패키지 기준 — 확인 필요) |
| 카메라 | YOLO 사람 감지용 (확인 필요) |
| 마이크 | VAD/STT 입력용 |
| 스피커 | TTS 출력용 |
| 네트워크 | Wi-Fi (동일 AP 연결) |

---

## 소프트웨어 스택

| 계층 | 기술 |
|------|------|
| OS | Ubuntu (Jetson 호환 버전) |
| 미들웨어 | ROS 2 |
| DDS | CycloneDDS (유니캐스트) |
| SLAM | Cartographer (wego 패키지 내장) |
| 경로 계획 | Nav2 |
| 위치 추정 | AMCL (Nav2 내장) |
| 행동 트리 | BehaviorTree.CPP (ROS 2 BT) + Nav2 BT |
| 음성 인식 | Silero VAD / openWakeWord / faster-whisper |
| NLU | If-else / Gemini API / Gemma-2B (Ollama, 폴백) |
| TTS | Piper (ONNX, 로컬) |
| 객체 인식 | YOLOv8 (사람 감지) |

---

## ROS 2 패키지 구성

```
ulsan_ws/src/
├── wego/                  # 기존: 로봇 기본 드라이버, Cartographer SLAM
├── wego_2d_nav/           # 기존: Nav2 기반 2D 경로 계획
├── wego_msgs/             # 기존: 공통 메시지 타입 정의
├── wego_bridge/           # 구현 완료: amcl_pose domain bridge (LIMO 전용)
├── ulsan_obstacle_layer/  # 구현 완료: 상대 로봇 amcl_pose → global costmap LETHAL_OBSTACLE 주입 (C++)
├── wego_ui/               # 구현 완료: RViz 기반 관제 UI (노트북 전용, 임시)
├── wego_behaviour/        # 뼈대 완료: Yasmin FSM (IDLE/GUIDING/RETURNING) + Nav2 연동
├── wego_voice/            # 미구현: 음성 파이프라인 (VAD→Wake→STT→NLU→TTS)
├── wego_aruco/            # 미구현: 홈 복귀 ArUco 보정
└── wego_coordinator/      # 미구현: on_duty 결정 (노트북 전용, laptop_ws)
```

---

## 미션 제어 구조 (wego_behaviour)

DEC-014: 최상단은 **Yasmin FSM**, 실행 레이어는 **Nav2 BT** (하이브리드).

```
wego_coordinator (노트북)
  /on_duty → wego_behaviour FSM
                │
                ├── IDLE
                │   └── /goal_destination 수신 대기 (wego_voice → NLU 결과)
                │
                ├── GUIDING
                │   └── navigate_to_pose(목적지 좌표) → Nav2 BT 위임
                │
                └── RETURNING
                    └── navigate_to_pose(home 좌표) → Nav2 BT 위임
                        └── 홈 도착 → wego_aruco 서비스 호출 (정밀 보정)
```

`wego_behaviour`는 **어디로 갈지** 결정만 담당. 실제 주행은 **Nav2 내부 BT**에 위임 (경로 계획·장애물 회피·복구 포함).

### Nav2 BT 커스텀 노드 (구현 예정, DEC-014)

| 노드 | 타입 | 역할 |
|------|------|------|
| `VoiceTriggerCondition` | Condition | 웨이크워드 감지 여부 확인 |
| `PeerRobotBusyCondition` | Condition | 상대 로봇 BUSY 여부 확인 |

---

## 데이터 흐름 요약

```
마이크 입력
  → Silero VAD (사람 목소리 확인)
    → openWakeWord ("헤이 리모" 감지)
      → faster-whisper STT (발화 텍스트 변환, Orin CUDA)
        → NLU (if-else 단순 목적지 / Gemini API 복합 의도)
          → Piper TTS (음성 응답)
          → wego_behaviour BT (목적지 결정)
            → Nav2 BT (경로 계획 + 실행)

카메라 입력 (RGB + Depth)
  → ulsan_person_detect (YOLOv8n + Depth 0.7m 게이팅) → /person_detected
    → Nav2 BT PersonClearCondition (RUNNING) → FollowPath halt → 주행 정지 (DEC-041)
    → (Phase 4) 방향 추정 → 회전 + 안내 멘트
```

---

## 주요 설계 결정 요약

| 결정 | 선택 | 이유 |
|------|------|------|
| DDS | CycloneDDS 유니캐스트 | 소규모 Wi-Fi 환경, 멀티캐스트 불필요 |
| 멀티로봇 분리 | amcl_pose 공유 (TF frame prefix 아님) | Open-RMF 동일 원칙. TF 트리 브릿징은 과설계. |
| 지도 공유 | 리더 지도 파일 복사 | 단일 환경, 실시간 공유 불필요 |
| 충돌 회피 | FleetObstacleLayer (amcl_pose → 가상 장애물 costmap 주입) | Nav2 기존 플래너 재사용, pose 기반 업계 표준 패턴 |
| STT 가속 | CUDA (Orin Nano 내장 GPU) | Whisper 실시간 처리 필수 |
| NLU 폴백 | Gemma-2B (Ollama 로컬) | 네트워크 단절 시 최소 기능 보장 |
| TTS | Piper (ONNX 로컬) | 지연 시간 최소화, 오프라인 동작 |

> 세부 결정 배경: [DECISION-LOG.md](../status/DECISION-LOG.md)
