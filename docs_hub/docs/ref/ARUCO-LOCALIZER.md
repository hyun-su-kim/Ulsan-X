# ArUco 마커 기반 정밀 도킹 설계 문서

> 관련 결정: DEC-016, DEC-018 | 담당 패키지: `wego_aruco`

## 적용 목적

홈 복귀 시 ArUco 마커를 이용한 visual servoing으로 정밀 정차 후 AMCL drift를 리셋한다.

- Nav2(AMCL)의 누적 drift를 매 안내 사이클마다 홈 복귀 시 보정
- **Coarse-to-Fine 패턴**: Nav2 대략 이동 → ArUco visual servoing 정밀 정차 → /initialpose 리셋
- MiR, Fetch 등 상용 AMR 및 Nav2 opennav_docking과 동일한 산업 표준 패턴

## 마커 구성

- 마커 수: **2개** (LIMO1용 ID 0, LIMO2용 ID 1)
- 부착 위치: 각 로봇 홈 위치 **정면** 벽 (로봇이 홈에 서면 카메라 정면에 마커)
- 각 로봇은 자신의 마커 ID만 추적

## 동작 흐름

```
Nav2로 홈 근처 이동 (±10~30cm)
    ↓
/aruco_correct 서비스 호출
    ↓ [wego_aruco 내부]
    마커 ID 감지
    dist_err = depth - target_dist
    lat_err  = lateral offset
    P제어 → cmd_vel 발행 (loop)
    오차 threshold 이내 → 정차
    ↓
정차 완료 응답 수신
    ↓
waypoints.yaml home 좌표 → /initialpose 발행 (AMCL 리셋)
    ↓
IDLE
```

## 패키지 구조

```
ulsan_ws/src/wego_aruco/
├── wego_aruco/
│   ├── __init__.py
│   └── aruco_localizer.py      # visual servoing 노드
├── config/
│   └── markers.yaml            # 마커 ID / size / target_dist
├── launch/
│   └── aruco_localizer_launch.py
├── package.xml
└── setup.py
```

## 마커 사양

| 항목 | 값 |
|------|-----|
| 딕셔너리 | `DICT_4X4_50` |
| 크기 | 10cm × 10cm |
| 재질 | 종이 인쇄 (A4) |
| 부착 위치 | 각 로봇 홈 정면 벽 (카메라 정면) |

## 노드 인터페이스

| 방향 | 토픽/서비스 | 타입 | 설명 |
|------|------------|------|------|
| Subscribe | `/camera/color/image_raw` | `sensor_msgs/Image` | 컬러 이미지 |
| Subscribe | `/camera/color/camera_info` | `sensor_msgs/CameraInfo` | 카메라 내부 파라미터 |
| Publish | `/cmd_vel` | `geometry_msgs/Twist` | visual servoing 제어 |
| Service | `/aruco_correct` | `std_srvs/Trigger` | 정밀 정차 요청 |

> `/initialpose` 발행은 `wego_behaviour` ReturningState에서 담당 (정차 완료 후 home 좌표 전송)

## P 제어 파라미터 (aruco_localizer.py 클래스 상수)

| 상수 | 기본값 | 설명 |
|------|--------|------|
| `KP_LINEAR` | 0.4 | 전진/후진 게인 |
| `KP_ANGULAR` | 0.8 | 회전 게인 |
| `MAX_LINEAR` | 0.15 m/s | 최대 전진 속도 |
| `MAX_ANGULAR` | 0.4 rad/s | 최대 회전 속도 |
| `DIST_TOL` | 0.03 m | 거리 허용 오차 |
| `LAT_TOL` | 0.03 m | 측면 허용 오차 |
| `TIMEOUT_SEC` | 30.0 s | 수렴 타임아웃 |

## markers.yaml 형식

```yaml
markers:
  0:                  # LIMO1 홈 마커
    size: 0.10        # 마커 한 변 길이 (m)
    target_dist: 0.30 # 정차 목표 거리 (m) — 실기기 조정 필요
  1:                  # LIMO2 홈 마커
    size: 0.10
    target_dist: 0.30

home_marker:
  home_robot1: 0
  home_robot2: 1
```

## 실행 방법

```bash
# LIMO1
ros2 launch wego_aruco aruco_localizer_launch.py home_key:=home_robot1

# LIMO2
ros2 launch wego_aruco aruco_localizer_launch.py home_key:=home_robot2
```

## 주의사항

- `target_dist`는 실기기에서 마커 부착 높이와 카메라 각도에 따라 조정 필요
- 카메라 실제 토픽명은 Orbbec 드라이버 기동 후 `ros2 topic list`로 확인
- visual servoing 중 Nav2와 cmd_vel 충돌 없음 — Nav2가 1차 이동 완료 후 서비스 호출
