# ArUco 마커 기반 정밀 도킹 설계 문서

> 관련 결정: DEC-029(방식 선택) · DEC-038(제어기 재설계) · DEC-041(AMCL 리셋) · DEC-042(polar 제거)
> 담당 패키지: `wego_aruco` | 노드: `aruco_home_dock`

## 적용 목적

홈 복귀 시 ArUco 마커 기반 **PBVS(Position-Based Visual Servoing)** 로 정밀 정차한 뒤 AMCL drift를 리셋한다.

- Nav2(AMCL)의 누적 drift를 매 안내 사이클 홈 복귀 시 보정
- **Coarse-to-Fine 패턴**: Nav2가 staging까지 대략 이동 → ArUco PBVS로 마지막 ~0.5m 정밀 정차 → `/initialpose` 리셋
- MiR·Fetch 등 상용 AMR 및 Nav2 `opennav_docking`과 동일한 산업 표준 패턴

### 왜 PBVS인가 (IBVS 아님)

`solvePnP`로 마커의 **3D 포즈(tvec/rvec)를 명시적으로 복원**하고, 오차를 로봇 기준 **작업공간(SE(2): ρ·α·θ_g)** 에서 정의해 제어한다 → **PBVS**. 이미지 평면 픽셀 오차를 image Jacobian으로 직접 제어하는 IBVS와 다르다. 코너 픽셀은 `solvePnP`의 입력일 뿐, 제어 루프는 복원된 기하에서 돈다.

## 마커 구성

- 마커 수: **2개** (LIMO1 ID 0, LIMO2 ID 1), 딕셔너리 `DICT_4X4_50`, 크기 **20cm**
- 부착 위치: 각 로봇 홈 정면 벽 (홈에 서면 카메라 정면에 마커)
- 각 로봇은 `ROS_DOMAIN_ID`로 자신의 `home_key`→마커 ID만 추적 (6→home_robot1→ID 0, 7→home_robot2→ID 1)

## 문제 정의 — 비홀로노믹 과소구동

차동구동 로봇은 입력이 (v, ω) 2개뿐인데 도킹은 depth·lateral·yaw 3개를 맞춰야 함 → 과소구동(underactuated). 초기 단순 합산 P제어(`ω = -Kp_w·lateral - Kp_yaw·yaw`)는 lateral·yaw 보정이 ω 하나를 공유하며 서로 상쇄(fight) → 목표 근처 교착·수렴 실패 (DEC-038에서 폐기).

→ 도킹 목표점의 로봇 기준 기하 **(ρ, α, θ_g)** 로 통합해 해결.

## 도킹 목표점 기하 (`_compute_geometry`)

도킹 목표점 = 마커 법선 위, 마커로부터 `target_dist` 떨어진(로봇 쪽) 지점.

| 기호 | 의미 |
|------|------|
| `ρ`   | 로봇 → 목표점 거리 |
| `α`   | 로봇 heading 대비 목표점 방향각 (조준 오차) |
| `θ_g` | 목표점에서 마커를 정면으로 보는 최종 heading 오차 |

좌표 변환: 카메라 optical(x=우, y=하, z=전) → 로봇 2D(x=전, y=좌): `robot_x = cam_z`, `robot_y = -cam_x`. 마커 법선(마커 z축)도 동일 변환 후 정규화하여 목표점 산출.

## 동작 흐름 — staged 3단계 (`_ctrl_staged`)

LIMO의 제자리 회전을 활용해 위치(안정적 lateral)는 직진으로, 자세는 단계 회전으로 분리한다.

```
Nav2로 staging 이동 (home 정면 ~0.5m)
    ↓
/aruco_home_dock 서비스 호출 (Trigger)
    ↓ [aruco_home_dock 내부, solvePnP → ρ,α,θ_g]

  ── Phase 0: 목표점 조준 (제자리 회전) ──────────────
     |α| < alpha_tol 까지 ω = kp_turn · α 로 회전

  ── Phase 1: 목표점까지 직진 (+조향 유지) ───────────
     v = kp_drive · ρ,  steer = kp_steer · α
     ※ ρ < steer_freeze 구간: α가 atan2 특이점으로 폭발 →
       조향 끄고 직진만 (lateral 잔차 수용)
     ρ < rho_tol → Phase 2

  ── Phase 2: 마커 정면 정렬 (제자리 회전) ───────────
     ω = kp_turn · θ_g
     (정렬 중 ρ > rho_tol×2 이탈 시 Phase 1 복귀)

    ↓ 수렴: ρ < rho_tol AND |θ_g| < yaw_tol
정차 → /initialpose 발행 (AMCL 리셋) → 완료 응답
```

> **전진만 허용**: `v = clip(v, 0, max_linear)` — 후진 시 마커가 카메라 FOV를 벗어나는 것 방지.

### 제어기 선택 근거 (A/B 실험 → staged 단독)

극좌표(Lyapunov 안정, polar)와 단계분리(staged) 두 제어기를 실기기 A/B 비교(DEC-038):

- **staged 채택**: lateral 0.8~1.7cm 안정 정차
- **polar 기각**: lateral은 수렴하나 ω가 ±0.3에 상시 포화하며 심한 S자 사행
- **근본 원인**: 단일 평면 마커 법선(out-of-plane 회전) 관측성이 낮아 노이즈가 큼. polar는 이 노이즈를 고게인(k_α=2.0)으로 ω에 직접 추종 → 사행. staged는 위치(ρ, 직진)와 자세(θ_g, 제자리 회전)를 시간적으로 분리해 노이즈 영향을 격리.
- **2026-06-01 (DEC-042)**: A/B 실험 종료, polar 제어기·`dock_mode` 파라미터 코드/런치에서 제거 → staged 단독.

## AMCL 리셋 방식 (`_publish_initialpose`, DEC-041)

도킹 완료 후 **마커 역산이 아니라 `waypoints.yaml`의 home 좌표를 직접 `/initialpose`로 발행**한다.

- 기존(폐기): 마커 rvec/tvec으로 T_map_base 역산 → 단일 평면 마커 정면 근처 yaw 관측성 한계로 **yaw 140° 오차** (실기기 확인)
- 현재: "PBVS 도킹 성공 = 로봇은 정의상 home 위치에 있다"는 사실을 활용 → home 좌표 결정론적 발행
- **결과**: 마커의 맵 좌표(map_pose)가 운영 경로에서 불필요해짐 → `markers.yaml`에서 제거 (아래 참조)

## 패키지 구조

```
ulsan_ws/src/wego_aruco/
├── wego_aruco/
│   ├── aruco_home_dock.py     # PBVS staged 도킹 서비스 노드 (운영)
│   └── aruco_measure.py       # 마커 상대 포즈(거리·각도) 실시간 측정 도구
├── config/
│   └── markers.yaml           # 마커 ID / size + home_marker 매핑
├── launch/
│   └── aruco_corrector_launch.py   # aruco_home_dock 실행
├── package.xml
└── setup.py
```

## 노드 인터페이스 (`aruco_home_dock`)

| 방향 | 토픽/서비스 | 타입 | 설명 |
|------|------------|------|------|
| Subscribe | `/camera/color/image_raw`   | `sensor_msgs/Image`      | 컬러 이미지 |
| Subscribe | `/camera/color/camera_info` | `sensor_msgs/CameraInfo` | 카메라 내부 파라미터(공장 캘리브레이션) |
| Publish   | `/cmd_vel`                  | `geometry_msgs/Twist`    | PBVS 제어 |
| Publish   | `/initialpose`              | `geometry_msgs/PoseWithCovarianceStamped` | 정차 후 AMCL 리셋(home 좌표) |
| Service   | `/aruco_home_dock`          | `std_srvs/Trigger`       | 정밀 정차 요청 |

> `wego_behaviour`는 RETURNING 상태에서 staging 도착 후 `/aruco_home_dock`를 호출하고 완료 응답만 수신.

## 파라미터 (`aruco_corrector_launch.py` 기준)

| 파라미터 | 값 | 설명 |
|----------|-----|------|
| `target_dist` | 0.505 | 마커 법선 위 도킹 목표점 거리(카메라 depth 실측, `aruco_measure`로 재측정 2026-06-01) |
| `rho_tol`     | 0.01  | 목표점 위치 수렴 허용오차 (m) — 1cm 정밀 (2026-06-01) |
| `yaw_tol`     | 0.02  | 최종 자세 θ_g 수렴 허용오차 (rad) ≈1.15° (2026-06-01, 측정 노이즈 ±0.5° 위 한계값) |
| `max_linear`  | 0.08  | 최대 선속도 (m/s) |
| `max_angular` | 0.3   | 최대 각속도 (rad/s) |
| `kp_turn`     | 0.8   | 제자리 회전 게인 (Phase 0·2) |
| `kp_drive`    | 0.4   | 직진 게인 (Phase 1) |
| `kp_steer`    | 0.6   | 직진 중 조향 게인 (Phase 1) |
| `alpha_tol`   | 0.05  | Phase 0 조준 완료각 (rad) |
| `steer_freeze`| 0.15* | 이 거리 이내면 α 조향 정지(목표 근처 α 폭발 방지) |
| `timeout_sec` | 30*   | 도킹 타임아웃 (s) |
| `no_marker_timeout_sec` | 5* | 마커 미감지 타임아웃 (s) |

> `*` 표시는 런치에서 미지정 → 노드 기본값 사용. `home_key`는 `ROS_DOMAIN_ID`(6/7)로 자동 결정.

## markers.yaml 형식

```yaml
markers:
  0:                  # 로봇1 홈 마커
    size: 0.20        # 마커 한 변 길이 (m) — solvePnP 미터 스케일 기준
  1:                  # 로봇2 홈 마커
    size: 0.20

home_marker:          # home_key → marker_id 매핑
  home_robot1: 0
  home_robot2: 1
```

- 도킹 노드(`aruco_home_dock`)가 읽는 필드는 **`size`와 `home_marker`뿐**.
- **map 좌표(`map_x/y/z`·`map_q*`·`calibrated`)는 제거됨 (DEC-041)**: 마커 역산 기반 보정을 폐기하고 home 좌표를 직접 발행하므로 운영에 불필요.

## aruco_measure (마커 상대 포즈 측정 도구)

마커의 **카메라 기준 상대 포즈**(거리·각도)를 매 프레임 콘솔에 출력하는 측정 도구. PBVS 도킹은 마커 맵 좌표가 필요 없고 상대 포즈만 쓰므로(DEC-041/043), 마커를 옮겨가며 거리·정렬을 확인하거나 `target_dist`를 실측·튜닝할 때 쓴다. 별도 토픽 echo 불필요(노드 로그만 보면 됨).

```bash
export ROS_DOMAIN_ID=6
ros2 run wego_aruco aruco_measure
# 다른 마커/크기: --ros-args -p marker_id:=1 -p marker_size:=0.20
```

출력 (축·yaw 정의는 `aruco_home_dock`과 동일):
```
id=0  depth=0.505m  lateral=+0.004m  height=-0.017m  dist=0.505m  yaw=-0.6°
=== 평균(30프레임) ===  depth=0.505±0.000  lateral=+0.004±0.000  ... yaw=-0.6±0.5° ===
```
- `depth` 전방거리(target_dist 기준) / `lateral` 좌우(우+, 0=정면) / `height` 상하(하+, 2D 도킹 무관)
- `dist` 직선거리 / `yaw` 마커 정면 대비 각

> 이전 `pose_corrector.py`(마커 맵 좌표 캘리브레이션 도구)는 DEC-041로 map_pose 경로가 폐기되어 비기능 상태였고, 2026-06-01 삭제됨. 측정 용도는 `aruco_measure`로 대체.

## 실행 방법

```bash
# domain 6 → home_robot1 / domain 7 → home_robot2 자동 선택
export ROS_DOMAIN_ID=6
ros2 launch wego_aruco aruco_corrector_launch.py
```

## 한계 (단일 평면 마커)

- 정면 근처에서 마커 법선(out-of-plane 회전) 관측성이 낮아 `θ_g` 신뢰도 제한. staged는 안정적인 lateral 위주 제어로 이를 우회.
- 더 높은 자세 정밀도가 필요하면 **마커 2개로 자세 삼각측량** 권장.

## 구현 현황 (2026-06-01)

| 항목 | 상태 |
|------|------|
| solvePnP 기반 마커 포즈 추정 | 완료 |
| PBVS staged(turn→drive→turn) 제어 | 완료 (DEC-038) |
| polar vs staged A/B 실기기 비교 | 완료 — staged 채택, lateral ~1cm |
| polar 제어기 제거 (staged 단독) | 완료 (DEC-042, 2026-06-01) |
| AMCL 리셋 = home 좌표 직접 발행 | 완료 (DEC-041) — 마커 역산 yaw 140° 오차 해결 |
| markers.yaml map_pose 제거 | 완료 (2026-06-01) |
| pose_corrector.py 삭제 + aruco_measure 신규 | 완료 (2026-06-01) |
| 정밀 정차 튜닝 (target_dist 0.505·rho_tol 0.01·yaw_tol 0.02) | 완료 (2026-06-01, LIMO1 실기기 정밀주차 확인) |
| LIMO1(ID 0) end-to-end 도킹 | 완료 |
| LIMO2(ID 1) 도킹 검증 | **미완료** (LIMO 2 현장 검증 필요) |
