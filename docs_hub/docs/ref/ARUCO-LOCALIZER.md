# ArUco 마커 기반 AMCL 보정 — 설계 문서

> 관련 결정: DEC-016 | 담당 패키지: `wego_aruco`

## 문제 배경

유리 회전문 구간에서 LiDAR 스캔 특징점이 없어 AMCL 파티클이 수렴하지 못하고 로봇이 제자리에서 회전하는 문제 발생 (2026-04-28 실기기 확인).

해결 전략: 유리 구간 벽에 ArUco 마커를 부착 → 카메라로 마커 감지 → 로봇 맵 좌표를 `/initialpose`로 AMCL에 주입 → 파티클 강제 재수렴.

---

## 패키지 구조

```
ulsan_ws/src/wego_aruco/
├── wego_aruco/
│   ├── __init__.py
│   └── aruco_localizer.py      # 핵심 노드
├── config/
│   └── markers.yaml            # 마커 ID → 맵 좌표 매핑
├── launch/
│   └── aruco_localizer_launch.py
├── package.xml
└── setup.py
```

---

## 마커 사양

| 항목 | 값 |
|------|-----|
| 딕셔너리 | `DICT_4X4_50` |
| 크기 | 10cm × 10cm |
| 재질 | 종이 인쇄 (A4) |
| 부착 위치 | 유리 구간 양쪽 벽 (카메라 시야 내) |

---

## 동작 흐름

```
/camera/color/image_raw       ─┐
/camera/color/camera_info     ─┤
                                ↓
                  cv2.aruco.detectMarkers()
                                ↓
                  estimatePoseSingleMarkers()
                  → T_camera_marker (카메라 기준 마커 pose)
                                ↓
                  markers.yaml 조회
                  → T_map_marker (맵 기준 마커 pose)
                                ↓
                  T_map_base = T_map_marker × T_marker_camera × T_camera_base
                                ↓
                  /initialpose (PoseWithCovarianceStamped) 발행
                                ↓
                  AMCL 파티클 재수렴
```

---

## Pose 계산 원리

1. `estimatePoseSingleMarkers()`로 카메라 기준 마커 위치 `T_camera_marker` 획득
2. `markers.yaml`에서 해당 마커의 맵 좌표 `T_map_marker` 조회
3. 역변환: `T_map_camera = T_map_marker × inv(T_camera_marker)`
4. TF에서 `T_camera_base` (`camera_link` → `base_link`) 조회
5. 최종: `T_map_base = T_map_camera × T_camera_base`

---

## markers.yaml 형식

```yaml
# 마커 ID → 맵 좌표 (map frame 기준)
# 좌표는 Nav2 실주행 후 RViz에서 확인하여 입력
markers:
  0:
    x: 0.0      # TODO: 실측 후 입력
    y: 0.0
    yaw: 0.0    # 마커 전면이 바라보는 방향 (rad)
    size: 0.10  # 마커 한 변 길이 (m)
  1:
    x: 0.0
    y: 0.0
    yaw: 3.14159
    size: 0.10
```

---

## 노드 인터페이스

| 방향 | 토픽 | 타입 | 설명 |
|------|------|------|------|
| Subscribe | `/camera/color/image_raw` | `sensor_msgs/Image` | Orbbec Astra 컬러 이미지 |
| Subscribe | `/camera/color/camera_info` | `sensor_msgs/CameraInfo` | 카메라 내부 파라미터 |
| Publish | `/initialpose` | `geometry_msgs/PoseWithCovarianceStamped` | AMCL 초기 위치 주입 |

### 파라미터

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `markers_file` | `config/markers.yaml` 경로 | 마커 좌표 파일 |
| `correction_interval` | `1.0` (sec) | 보정 발행 최소 간격 (중복 발행 방지) |
| `min_marker_area` | `500` (px²) | 너무 작은 마커 감지 무시 임계값 |

---

## 구현 단계

### Step 1 — 패키지 뼈대 생성
- `wego_aruco` ament_python 패키지 생성
- 의존성: `rclpy`, `cv_bridge`, `opencv-python`, `tf2_ros`, `geometry_msgs`

### Step 2 — aruco_localizer.py 구현
- 카메라 이미지 구독 + ArUco 감지
- `markers.yaml` 로드 + pose 계산
- `/initialpose` 발행 (일정 간격 제한)

### Step 3 — markers.yaml 좌표 입력
- Nav2 실주행하며 RViz에서 마커 부착 예정 위치 좌표 확인
- 마커 부착 후 좌표 입력

### Step 4 — 실기기 검증
- 카메라 토픽명 확인 (`ros2 topic list` 후 실제 토픽명으로 수정)
- 유리 구간 통과 시 AMCL 파티클 수렴 확인

---

## 실행 방법

```bash
# Nav2 스택 실행 후 추가로 실행
ros2 launch wego_aruco aruco_localizer_launch.py
```

---

## 주의사항

- 카메라 실제 토픽명은 Orbbec 드라이버 기동 후 `ros2 topic list`로 확인 필요
- `markers.yaml` 좌표는 Nav2 실주행 후 RViz에서 확인하여 입력 (현재 TODO)
- 조명이 매우 어두운 경우 인식률 저하 가능 → 유리 구간 조명 확보 권장
