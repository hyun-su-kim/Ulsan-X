# NAVIGATION — SLAM & Nav2 설정

## SLAM 도구 선택 경위 (2026-05-05)

### 1차 매핑 — Cartographer (2026-04-28~29)

초기에 Cartographer를 선택한 이유:
- 복도·유리 구간이 많은 학원 환경에서 submap 기반 loop closure 성능이 검증됨
- ROS2 Humble 공식 패키지로 설치 간편

결과: 맵 작성 및 Nav2 자율주행은 동작했으나, 장시간 운용 후 **홈 복귀 위치 오차가 허용 범위를 초과**하는 문제 발생.

### 재매핑 결정 및 SLAM Toolbox 전환 (2026-05-05)

**문제 정의**: 홈 복귀 위치 오차의 원인이 ① SLAM 맵 품질 문제인지, ② AMCL 로컬라이저 drift 문제인지 구분이 필요했음.

**SLAM Toolbox로 전환한 기술적 근거**:

| 비교 항목 | Cartographer | SLAM Toolbox |
|----------|-------------|-------------|
| 저장 포맷 | `.pbstream` (독자 포맷) | `.posegraph` + `.data` + PGM |
| AMCL 연동 | PGM 저장 후 사용 가능 | PGM 저장 후 사용 가능 |
| SLAM Toolbox localization | **불가** (포맷 불일치) | **가능** (동일 포맷) |
| ROS2 공식 권장 | community maintained | Nav2 기본 SLAM |
| 복도 환경 loop closure | 강함 (submap 교차 검증) | 충분 (전역 포즈 그래프 최적화) |

**핵심 이유**: 원인 규명을 위해 **AMCL(파티클 필터) vs SLAM Toolbox localization(scan matching)** 두 방식을 동일 맵 위에서 정량 비교할 계획. 이를 위해 `.posegraph` 포맷이 필요하고, Cartographer SLAM으로는 생성 불가. SLAM Toolbox로 SLAM하면 PGM(AMCL용) + posegraph(SLAM Toolbox localization용) 둘 다 한 번에 확보 가능.

> **면접 어필**: "홈 복귀 오차의 원인을 SLAM 품질과 로컬라이저 drift로 분리해 진단하기 위해, 동일 맵 위에서 AMCL과 SLAM Toolbox localization을 정량 비교하는 실험을 설계했다. 이 비교를 위해 SLAM 단계부터 두 포맷을 동시에 저장할 수 있는 SLAM Toolbox를 선택했다."

---

## 지도 작성 (SLAM Toolbox — 2차 매핑, 2026-05-05~)

- **사용 패키지**: `wego` (`slam_toolbox_launch.py`)
- **파라미터**: `wego_2d_nav/params/slam_toolbox_slam_params.yaml`
- **작성 주체**: LIMO 1으로만 SLAM 수행. LIMO 2는 완성된 맵 파일 배포.
- **원점 설정**: 홈 위치에서 SLAM 시작 → 홈 = (0, 0, 0)
- **저장 포맷**: PGM + YAML (AMCL용), posegraph + data (SLAM Toolbox localization용)

```bash
# LIMO 1에서 실행

# Terminal 1: 드라이버 전체 기동
ros2 launch wego teleop_launch.py

# Terminal 2: SLAM Toolbox 매핑 시작
ros2 launch wego slam_toolbox_launch.py
# SSH 환경: ros2 launch wego slam_toolbox_launch.py use_rviz:=false

# Terminal 3: 키보드 텔레op으로 공간 주행
ros2 run teleop_twist_keyboard teleop_twist_keyboard

# 매핑 완료 후 — 두 포맷 모두 저장
# ① PGM 저장 (AMCL + 노트북 map_server용)
ros2 run nav2_map_server map_saver_cli -f ~/map_result/map

# ② posegraph 저장 (SLAM Toolbox localization용)
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
  "{name: {data: '/home/wego/map_result/slam_map'}}"
# → slam_map.posegraph + slam_map.data 생성

# 저장된 맵을 프로젝트에 복사 후 git push → 각 기기 git pull로 배포
cp ~/map_result/map.* \
  /home/wego/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/
cp ~/map_result/slam_map.* \
  /home/wego/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/
```

### SLAM 모드 설명 (async vs sync)

`async_slam_toolbox_node` 선택 이유:
- **async(비동기)**: 스캔 처리를 별도 스레드에서 수행 → 실시간 주행 중에도 맵 업데이트 끊김 없음
- sync는 스캔 처리 동안 다른 콜백이 블로킹됨 → 실기기 주행 시 TF 끊김 가능성

---

## SLAM 품질 향상 절차 (학원 환경 — 유리+복도)

Cartographer 1차 매핑 시 발생한 문제와 해결 절차. SLAM Toolbox 재매핑 시에도 동일하게 적용.

### 문제
- 유리 구간: LiDAR가 유리를 투과 → 특징점 없음 → 맵에 구멍
- 복도 구간: 양쪽 벽만 있는 긴 직선 → loop closure 실패 → 복도 휨(drift)

### 해결 절차

1. **유리에 종이 부착** — LiDAR 반사 특징점 확보. 매핑 완료 후 제거.
2. **복도 중간에 임시 장애물 배치** — 특징점 추가로 복도 drift 방지.
3. **홈 위치에서 시작** — 홈이 원점 (0, 0, 0)이 되어 waypoint 설정 직관적.
4. **천천히 루프 주행(왕복)으로 매핑**
   - RViz에서 `/map` 토픽 실시간 확인
   - 출발점(홈)으로 복귀 시 자동 loop closure 발생 → 복도 drift 보정
5. **맵 저장 후 임시 장애물 실제 환경에서 제거**
6. **GIMP로 후보정** — 장애물 흔적 및 스파이크 노이즈 제거
7. **가상 벽 처리** — 유리문 등 인식이 덜 된 구간을 GIMP로 직접 벽 그리기

### SLAM Toolbox loop closure 확인 방법

```bash
# loop closure 발생 시 터미널에 출력됨
# "RUNNING LOOP CLOSURE JOB" 메시지 확인
# RViz: /map 토픽에서 전체 맵 일관성 시각적 확인
```

---

## 위치추정 방식 비교 실험 (2026-05-05 계획, 실행 예정)

### 실험 목적

홈 복귀 오차의 원인이 SLAM 품질 문제인지 로컬라이저 drift 문제인지 수치로 분리·진단.
동시에 두 방식 중 더 강건한 로컬라이저를 선택하기 위한 근거 확보.

### 비교 대상

| | AMCL | SLAM Toolbox localization |
|--|--|--|
| 방식 | 파티클 필터 (확률적) | Scan matching + 포즈 그래프 최적화 (결정론적) |
| 발행 토픽 | `/amcl_pose` + `/tf` | `/tf` (map→odom)만 발행 |
| 맵 포맷 | `map.yaml` (PGM) | `slam_map.posegraph` |
| 파라미터 파일 | `diff_navigation_params.yaml` | `slam_toolbox_localization_params.yaml` |

> **SLAM Toolbox localization 주의**: `/amcl_pose`를 발행하지 않음.
> `wego_bridge`·`ulsan_obstacle_layer`는 `/amcl_pose` 의존. 비교 실험은 단일 로봇으로 진행하므로 문제 없음.
> 최종 선택 후 멀티로봇 단계에서 `/tf → /amcl_pose` republisher 노드 추가 예정 (SLAM Toolbox 선택 시).

### 측정 프로토콜

**측정 항목 3가지:**

#### ① 홈 복귀 반복 오차 (정밀도)
- 방법: 홈 → 목적지(가장 먼 강의실) → 홈 복귀, 10회 반복
- 측정: 복귀 완료 후 바닥 기준점 대비 로봇 앞바퀴 위치를 자로 측정 (x, y 각각)
- 기록: 10회 평균 오차, 최대 오차, 표준편차

#### ② 초기 수렴 속도
- 방법: 로봇 기동 후 `/amcl_pose` 또는 `/tf`의 covariance가 일정 값(0.1) 이하로 줄어드는 시간 측정
- 측정: `ros2 topic echo /amcl_pose` covariance 값 기록 (AMCL) / TF 안정화 시간 (SLAM Toolbox)

#### ③ 장거리 주행 후 drift
- 방법: 학원 전체 경로(전 목적지 순회) 1회 주행 후 홈 복귀
- 측정: 실제 홈 위치 vs 로봇 추정 위치 (RViz `/amcl_pose` 또는 TF 수치)
- 바닥 기준점과 비교하여 절대 오차 기록

### 실행 방법

```bash
# AMCL 로컬라이제이션
ros2 launch wego_2d_nav localization_launch.py  # map_server + amcl

# SLAM Toolbox localization 모드
ros2 launch wego_2d_nav slam_toolbox_localization_launch.py  # 구현 예정
```

### 결과 기록 양식 (실험 후 아래에 기입)

| 항목 | AMCL | SLAM Toolbox loc |
|------|------|-----------------|
| 홈 복귀 평균 오차 (m) | — | — |
| 홈 복귀 최대 오차 (m) | — | — |
| 초기 수렴 시간 (s) | — | — |
| 장거리 drift (m) | — | — |
| **선택** | | |

---

## 멀티로봇 위치 추정 구조

> DEC-011 (2026-04-21): TF frame prefix 방식 폐기 → **amcl_pose 공유 방식** 확정

### 설계 원칙

각 로봇은 표준 TF 프레임을 그대로 유지 (`base_link`, `odom`, `map`). prefix 없음.
위치 정보는 `/amcl_pose`만 domain bridge로 전달. `/tf` 브릿징 없음.

```
LIMO 1 (domain 6)            LIMO 2 (domain 7)
map → odom → base_link       map → odom → base_link
      ↓ /amcl_pose                  ↓ /amcl_pose
      [wego_bridge]                 [wego_bridge]
             ↓                             ↓
        노트북 (domain 5)
        /limo_1/amcl_pose   /limo_2/amcl_pose
             ↓                             ↓
        wego_ui (지도 위 위치 마커 시각화)
```

### 실행 방법

```bash
# LIMO 1, LIMO 2 동일한 명령 (robot_name 인자 없음)
ros2 launch wego teleop_launch.py
ros2 launch wego navigation_diff_launch.py
ros2 launch wego_bridge robot_bridge_launch.py  # ROS_DOMAIN_ID 읽어 자동 설정

# 노트북 (domain 5)
ros2 run nav2_map_server map_server --ros-args -p yaml_filename:=<path>/map.yaml
```

### 상대 로봇 충돌 회피 (ulsan_obstacle_layer)

```
상대방 /amcl_pose 수신 (domain bridge 경유)
  → PeerObstacleLayer: 해당 좌표에 반경 0.35m 원형 가상 장애물 생성
  → global costmap LETHAL_OBSTACLE 주입
  → Nav2 글로벌 플래너(A*)가 자동 우회 경로 생성
```

Nav2 플래너 수정 없이 적용 가능. `peer_pose_topic`을 비워두면 `ROS_DOMAIN_ID`로 자동 결정 (domain 6 → limo_2, domain 7 → limo_1).

---

## 위치 추정 (AMCL)

- **방식**: Nav2 내장 AMCL (Adaptive Monte Carlo Localization)
- **사용 센서**: LiDAR 스캔 (`/scan`)
- **초기 위치**: Home 위치에서 초기 pose estimate 설정

### 수정된 AMCL 파라미터 (`diff_navigation_params.yaml`)

| 파라미터 | 기본값 | 적용값 | 이유 |
|---------|--------|--------|------|
| `do_beamskip` | false | **true** | 유리 투과·난반사 빔 자동 무시 |
| `laser_max_range` | 12.0 | **12.0** | wego_ws 원본 복원 (실기기 테스트 결과 원본이 더 안정적) |

---

## Nav2 주행 문제 해결 과정 — 유리 구간 (2026-04-28~29)

포트폴리오·면접용 엔지니어링 판단 기록.

### 배경

SLAM 시에는 유리문에 종이를 부착해 LiDAR 특징점을 확보하고 맵을 완성했다.
실제 운용 환경에서는 종이가 없으므로, 유리 구간에서 LiDAR 스캔 특징점이 부족해질 수 있었다.

### 1단계 — AMCL 위치추정 문제 의심

**증상**: 유리 회전문 통과 구간에서 로봇이 빙글빙글 돌며 통과 못함.

**초기 가설**: 유리 구간에서 LiDAR가 특징점을 인식하지 못해 AMCL 파티클이 수렴하지 못하는 것 아닌가?

**조치**: AMCL 파라미터 수정
- `do_beamskip: true` — 유리 투과·난반사 빔 자동 무시
- `laser_max_range: 5.0` — 원거리 노이즈 제거

**결과**: RViz `/particlecloud` 확인 → 파티클이 유리 구간에서도 정상 수렴.
→ **위치추정은 문제가 아니었다.** 가설 기각.

### 2단계 — Inflation 조정 시도

복도·강의실 등 다른 구간은 주행 정상. 유리 회전문 구간만 빙글빙글 도는 현상 지속.

**가설**: 유리문 근처를 로봇이 지나갈 여유 공간이 부족한 것 아닌가?

**조치**: global costmap `inflation_layer`의 `inflation_radius` 확대 (유리문 근처 여유 공간 확보 목적)

**결과**: 해결되지 않음.

### 3단계 — Global Costmap 시각화로 원인 확인

**조치**: RViz에서 `/global_costmap/costmap` 토픽 직접 확인.

**관찰**: 유리 회전문 구간 주변에 실제 장애물이 없음에도 costmap 곳곳에 장애물(occupied cell)이 찍혀 있음.

**원인 확정**: **LiDAR 난반사(phantom obstacle)**
- LiDAR 빔이 유리를 투과하거나 난반사 → 실제 없는 위치에 장애물 포인트 생성
- 난반사 빔은 raytrace 경로와 달라 자동 소거가 안 됨 → 유령 장애물 지속
- 유령 장애물이 경로를 막음 → Nav2가 반복 리플래닝 → 빙글빙글

### 4단계 — 소프트웨어 해결 방법 전수 검토 (2026-04-29)

phantom 원인 확정 후 아래 방법들을 순서대로 시도·검토.

| 방법 | 시도 결과 |
|------|----------|
| `obstacle_max_range` 축소 | phantom이 2m 이내 → 효과 없음 |
| Keepout Filter (센서 무시 구역) | phantom이 폴리곤 밖에도 찍힘 → 효과 없음 |
| 맵 유리 연장 (GIMP) | 로봇 통과 경로 차단 → 포기 |
| `laser_filters` 각도 필터 | 회전 중 유리 방향 계속 바뀜 → 완벽 해결 불가 |
| `observation_persistence` 단축 | phantom이 매 스캔 동일 위치 재생성 → 효과 없음 |
| `clearing: False` + `combination_method` 조정 | phantom 누적 완화 시도했으나 근본 해결 안 됨 |

**VoxelLayer + Orbbec 카메라 검토 결과**: Orbbec Astra는 IR 구조광 방식으로 유리 투과 → depth 값 없음. LiDAR phantom보다 오히려 유리를 아예 못 잡음. 유리 감지 목적으로는 부적합.

### 최종 결정 — Keepout Filter (금지구역 방식) + DenoiseLayer

**Keepout Filter를 금지구역으로 사용** (센서 무시 구역이 아님):
- 유리 구간 주변에 금지구역 폴리곤 설정
- global planner가 해당 구역을 우회하는 경로 생성
- 로봇이 유리에 가까이 가지 않음 → 난반사 각도 감소 → phantom 감소
- Nav2 공식 문서 등재 기능, 상용 AMR(iRobot·Locus·Geek+)의 "가상 벽"과 동일 원리

**DenoiseLayer 추가**:
- Nav2 공식 플러그인 — 고립된 단일 셀 phantom 필터링
- 설정 거의 없이 바로 적용 가능
- Keepout Filter 경계 밖으로 새어나오는 phantom 보조 차단

### 5단계 — Keepout Filter + DenoiseLayer 적용 결과 (2026-04-29)

| 구간 | 결과 |
|------|------|
| 복도·강의실 등 일반 구간 | 정상 자율주행 |
| 목적지·홈 위치 주행 | 정상 — 운용 목적 달성 |
| **유리 회전문 통과 구간** | **여전히 `controller_server: Failed to make progress` 발생** |

**유리 회전문 통과가 안 되는 근본 이유**:
- Keepout Filter는 global costmap에만 적용 → global 경로는 우회하도록 생성됨
- 그러나 유리 근처를 지나는 경로라면 local costmap에 phantom이 여전히 찍힘
- local costmap의 phantom → DWB controller가 제어 명령 생성 실패 → 진행 불가
- 유리 회전문 자체를 통과하는 경로는 어떤 소프트웨어 설정으로도 LiDAR 물리 한계 극복 불가

**최종 운용 정책**:
- **유리 회전문 통과는 경로에서 영구 제외** — Keepout 금지구역으로 완전 차단
- 운용 목적(강의실·상담실·홈 안내 주행)에는 유리 회전문 통과가 불필요 → 실질적 문제 없음
- 유리문은 항상 열린 상태 유지 가정. 닫힘 감지(초음파 + TTS)는 Phase 4.

> **면접 어필 포인트**: "LiDAR의 물리적 한계(유리 투과·난반사)를 소프트웨어만으로 완전 해결할 수 없음을 실기기 검증으로 확인하고, 운용 목적에서 해당 구간을 제외하는 현실적 판단을 내렸다. 목적지 안내 주행이라는 서비스 요구사항 내에서는 완전 동작함."

### 6단계 — Keepout 경계 hugging 문제 해결 (2026-05-19)

Keepout 경계에 붙어 주행하다 일부 진입하는 문제가 추가로 발생. 근본 원인: global planner가 Keepout 경계 바깥 cost가 0에 가까워 경계에 최대한 붙는 최단 경로를 생성.

**해결**: `NavigateThroughPoses` + 통유리 사이 수직 경유 포인트 2개 (`glass_entry`, `glass_exit`) 삽입.

- 두 경유 포인트가 수직 통과선을 정의 → 플래너가 유리 구간 중앙을 통과하는 단일 전역 경로 생성
- 경유 포인트는 WaypointFollower(순차 정지)와 달리 정지 없이 통과 — 다른 BT XML 사용
- classroom_1~5는 유리 구간 미통과 → 기존 `goToPose` 유지
- 나머지 목적지(상담실·카운터·멀티룸·회의실) → `goThroughPoses([glass_entry, glass_exit, 목적지])`
- 복귀 시 순서 반전: `goThroughPoses([glass_exit, glass_entry, home])`
- 경유 포인트 yaw: 0.0 (플래너가 위치만으로 방향 결정, goal checker 미적용)

→ DEC-030 참고

---

## 목적지 관리 (waypoints.yaml)

목적지 좌표는 `wego_behaviour/config/waypoints.yaml`에서 중앙 관리.
`wego_behaviour` FSM이 읽어 `navigate_to_pose` 액션으로 전달.

좌표 기록 방법:
```bash
# Nav2 기동 후 teleop으로 목적지까지 이동 → 현재 pose 출력
ros2 topic echo /amcl_pose --once
# pose.pose.position.x, y 와 orientation.z, w → yaw = 2 * arctan2(z, w)
```

실제 목적지 목록 (좌표는 실주행 후 기록):
```yaml
waypoints:
  home_robot1:   { x: 0.0, y: 0.0, yaw: 0.0, label: "로봇1 홈" }
  home_robot2:   { x: 0.0, y: 0.0, yaw: 0.0, label: "로봇2 홈" }
  classroom_1~5: ...  # 유리 구간 미통과 → goToPose 직행
  counseling_1:  { x: 0.0, y: 0.0, yaw: 0.0, label: "상담실1" }
  counseling_2:  { x: 0.0, y: 0.0, yaw: 0.0, label: "상담실2" }
  intensive_counseling_1: { x: 0.0, y: 0.0, yaw: 0.0, label: "집중상담실1" }
  intensive_counseling_2: { x: 0.0, y: 0.0, yaw: 0.0, label: "집중상담실2" }
  vice_principal: { x: 0.0, y: 0.0, yaw: 0.0, label: "부원장실" }
  counter:       { x: 0.0, y: 0.0, yaw: 0.0, label: "카운터" }
  multi:         { x: 0.0, y: 0.0, yaw: 0.0, label: "멀티룸" }
  # 유리 구간 경유 포인트 (통유리 사이 수직선 양 끝) — 실측 후 기입
  glass_entry:   { x: 0.0, y: 0.0, yaw: 0.0, label: "유리구간 진입" }
  glass_exit:    { x: 0.0, y: 0.0, yaw: 0.0, label: "유리구간 탈출" }
```

---

## wego_behaviour FSM 연동

```
wego_dispatcher → /goal_destination (String 키, 예: "classroom_1")
  → wego_behaviour IDLE 상태 수신
  → waypoints.yaml에서 좌표 조회
  → blackboard['from_home'] = True 설정
  → GUIDING:
      [홈 출발 시] navigator.spin(180°) 선실행  ← DEC-037
        목적: AMCL 파티클 수렴 + Nav2에 180° 회전 부담 제거
      classroom_1~5 → navigate_to_pose(목적지)
      나머지        → navigate_through_poses([glass_entry, glass_exit, 목적지])
    → Nav2 내부 BT (경로 계획 + 장애물 회피 + 복구)
      → 도달 시 RETURNING 전환
        → classroom_1~5 → navigate_to_pose(home_staging)
          나머지        → navigate_through_poses([glass_exit, glass_entry, home_staging])
          → staging 도착 → PBVS 홈 도킹 (aruco_home_dock 서비스)
          → 홈 정밀 정차 → IDLE 복귀
```

**Progress Checker**: `SimpleProgressChecker` (선형 이동만 측정)
- 홈 출발 180° 회전은 Spin으로 선처리하므로 주행 시작 시 이미 방향 맞춰진 상태
- 주행 중 제자리 회전(stuck) 정확히 감지 → recovery 동작 정상 발동 (DEC-037)

`home_key`는 `ROS_DOMAIN_ID`로 자동 결정 (robot_config.yaml의 domain_home_map):
```bash
export ROS_DOMAIN_ID=6 && ros2 launch wego_behaviour behaviour_launch.py  # LIMO 1 → home_robot1
export ROS_DOMAIN_ID=7 && ros2 launch wego_behaviour behaviour_launch.py  # LIMO 2 → home_robot2
```

---

## Fleet 충돌 회피 (ulsan_obstacle_layer)

상대 로봇을 동적 장애물로 인식시키는 방식.

```
/limo_N/amcl_pose 수신 (Domain Bridge 경유)
  → ulsan_obstacle_layer (PeerObstacleLayer): 해당 좌표에 반경 R의 원형 가상 장애물 생성
  → global costmap에 LETHAL_OBSTACLE로 주입
  → Nav2 글로벌 플래너(NavFn/A*)가 자동으로 우회 경로 생성
```

**장점**: Nav2 기존 플래너 수정 없이 충돌 회피 가능.
**고려사항**: 로봇 실제 크기 + 안전 마진을 반경 R에 반영할 것.

---

## 로봇 복귀 흐름

```
목적지 도달 (Nav2 action 성공)
  → TTS: "다른 도움이 필요하시면 말씀해 주세요"  (구현 예정)
  → STT 짧게 대기 (타임아웃: ~10s)              (구현 예정)
    ├── 추가 요청 있음 → 새 목적지로 안내
    └── 없음 / 타임아웃
          → RETURNING: navigate_to_pose(home_robotN)
              → 홈 도착
                → wego_aruco 서비스 호출 → ArUco 마커 감지 → /initialpose 보정
                → IDLE 복귀
```

ArUco 보정은 홈에만 적용 (DEC-016). 목적지 도착 시 보정 없음 — Nav2 정밀도로 충분.
