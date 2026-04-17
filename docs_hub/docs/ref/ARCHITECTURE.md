# ARCHITECTURE — AI 기반 학원 안내 로봇

## 시스템 개요

```
[ 학원 입구 ]
  ┌─────────────┐    ┌─────────────┐
  │  리더 로봇   │    │  서브 로봇   │
  │  (Robot 1)  │    │  (Robot 2)  │
  │ DOMAIN_ID=6 │    │ DOMAIN_ID=7 │
  └──────┬──────┘    └──────┬──────┘
         │  /amcl_pose (유니캐스트)  │
         └──────────┬────────────────┘
                    │
          ┌─────────▼──────────┐
          │   서버 노트북       │
          │   DOMAIN_ID=5      │
          │   관제 UI (추후)    │
          └────────────────────┘
```

**원칙**: 리더 로봇이 대기(idle) 상태일 때만 서브 로봇은 대기. 리더가 busy(안내 중/복귀 중)이면 서브가 활성화. → 우선순위 기반 임무 할당.

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
├── wego_fleet/            # 신규: 상대 로봇 위치 → 가상 장애물 변환
├── wego_behaviour/        # 신규: 최상단 Behavior Tree (임무 관리)
└── wego_voice/            # 신규: 음성 파이프라인 (VAD→Wake→STT→NLU→TTS)
```

---

## 행동 트리 (Behavior Tree) 구조

```
wego_behaviour (최상단 BT)
│
├── [Fallback] 로봇 활성화 조건
│   ├── 리더 idle? → 리더 활성화
│   └── 리더 busy? → 서브 활성화
│
└── [Sequence] 안내 임무
    ├── [대기 상태]
    │   ├── YOLO 사람 감지 → 주기적 안내 멘트 발화
    │   └── VAD → openWakeWord "헤이 리모" 감지
    │
    ├── [호출 응답]
    │   ├── YOLO 방향으로 로봇 회전
    │   ├── "어떤 도움을 드릴까요?" TTS
    │   └── STT → NLU 명령 해석
    │
    ├── [안내 임무] → Nav2 BT에 목적지(waypoint) 전달
    │
    └── [복귀]
        ├── 목적지 도달 후 추가 용무 확인
        └── 없으면 Home 좌표로 Nav2 복귀
```

`wego_behaviour`는 최상단 결정만 담당. 실제 주행은 **Nav2 BT**에 위임.

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

카메라 입력
  → YOLOv8 (사람 감지 + 방향 추정)
    → 주기적 안내 멘트 트리거 (10~20s)
    → 호출 시 로봇 회전 방향 결정
```

---

## 주요 설계 결정 요약

| 결정 | 선택 | 이유 |
|------|------|------|
| DDS | CycloneDDS 유니캐스트 | 소규모 Wi-Fi 환경, 멀티캐스트 불필요 |
| 지도 공유 | 리더 지도 파일 복사 | 단일 환경, 실시간 공유 불필요 |
| 충돌 회피 | 가상 장애물 costmap 주입 | Nav2 기존 플래너 재사용 가능 |
| STT 가속 | CUDA (Orin Nano 내장 GPU) | Whisper 실시간 처리 필수 |
| NLU 폴백 | Gemma-2B (Ollama 로컬) | 네트워크 단절 시 최소 기능 보장 |
| TTS | Piper (ONNX 로컬) | 지연 시간 최소화, 오프라인 동작 |

> 세부 결정 배경: [DECISION-LOG.md](../status/DECISION-LOG.md)
