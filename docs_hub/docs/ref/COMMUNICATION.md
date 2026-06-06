# COMMUNICATION — CycloneDDS & Domain Bridge 설정

## 선택 배경

| 항목 | 선택 | 이유 |
|------|------|------|
| DDS 구현체 | CycloneDDS | 소규모 Wi-Fi 환경에 최적화, 안정성 검증됨 |
| 통신 방식 | 멀티캐스트 (CycloneDDS 기본) | cyclone_peers.xml 제거 — 동일 AP 환경에서 자동 discovery로 충분 |
| Domain 분리 | ros2-domain-bridge | 필요한 토픽만 선택적 브릿징, 트래픽 최소화 |

---

## CycloneDDS 설정

`cyclone_peers.xml` **삭제됨** (2026-05-25). CycloneDDS 기본 멀티캐스트 auto-discovery 사용.

```bash
# CYCLONEDDS_URI 환경변수 설정 불필요
# RMW_IMPLEMENTATION만 설정
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

> 동일 AP(공유기)에 연결된 기기 간에는 CycloneDDS 기본 멀티캐스트 discovery로 자동 연결됨.
> 멀티캐스트 지원 AP 사용 필수. 5GHz 대역 권장 (TS-001 참고).

---

## Domain ID 설정 (확정)

| 기기 | DOMAIN_ID | 실행 내용 |
|------|-----------|-----------|
| 데스크탑 | **6** | Nav2 + behaviour + voice + bridge (LIMO 1 담당) |
| 데스크탑 | **7** | Nav2 + behaviour + voice + bridge (LIMO 2 담당) |
| 데스크탑 | **5** | traffic + dispatcher + FastAPI(MySQL) |
| 노트북 | **5** | ulsan_gui (관제 GUI, PyQt) 또는 ulsan-visitor-ui (방문자 UI) |
| LIMO 1 | **6** | 드라이버 + aruco + 사람감지 (perception 엣지, DEC-043) |
| LIMO 2 | **7** | 드라이버 + aruco + 사람감지 (perception 엣지, DEC-043) |

```bash
# 데스크탑 — LIMO 1 담당 터미널
export ROS_DOMAIN_ID=6

# 데스크탑 — LIMO 2 담당 터미널
export ROS_DOMAIN_ID=7

# 데스크탑 — 공통 서비스 터미널
export ROS_DOMAIN_ID=5

# 노트북 ~/.bashrc
export ROS_DOMAIN_ID=5

# LIMO 1 ~/.bashrc
export ROS_DOMAIN_ID=6

# LIMO 2 ~/.bashrc
export ROS_DOMAIN_ID=7
```

---

## ros2-domain-bridge 설정

**서버(데스크탑)의 LIMO 도메인 터미널에서 실행** (domain 6/7). 로봇이 아니라 서버에서 실행하며, `ROS_DOMAIN_ID`로 어느 로봇 브릿지인지 자동 결정한다.

### 실행 방법

```bash
# 서버 LIMO 도메인 터미널에서 동일한 명령 (leader 구분 없음 — DEC-012)
export ROS_DOMAIN_ID=6 && ros2 launch wego_bridge bridge_launch.py  # LIMO 1
export ROS_DOMAIN_ID=7 && ros2 launch wego_bridge bridge_launch.py  # LIMO 2
```

### 설계 (DEC-011, DEC-012, DEC-028)

- **단일 템플릿**: `wego_bridge/config/bridge_robot.yaml` — `ROBOT_DOMAIN`, `ROBOT_NAME` 플레이스홀더 (`to_domain: 5` 고정)
- **launch**: `bridge_launch.py`가 `ROS_DOMAIN_ID`를 읽어 `robot_config.yaml`에서 `robot_name`을 결정 → 템플릿의 `ROBOT_DOMAIN`/`ROBOT_NAME` 치환 후 실행
- **`/map`**: 브릿징 없음. 각 기기가 로컬 map_server로 독립 발행 (DEC-012)
- **`/amcl_pose`**: 각 로봇 → domain 5(노트북)로만 전송. **로봇↔로봇 peer 브릿징 없음** (PeerObstacleLayer 폐기 DEC-022). wego_traffic이 domain 5에서 두 pose를 받아 거리 계산.

### 브릿지 토픽

`bridge_robot.yaml` 단일 템플릿 (ROBOT_DOMAIN/ROBOT_NAME 치환, DEC-028). **로봇↔domain 5만 브릿징** — 로봇↔로봇 peer 브릿징은 FleetObstacleLayer 폐기(DEC-022)로 제거됨.

| 토픽 | 방향 | 목적 (구독자) |
|------|------|--------------|
| `/amcl_pose` | robot → 5 | wego_traffic 거리감지, ulsan_gui 위치 마커 |
| `/robot_status` | robot → 5 | wego_traffic, wego_dispatcher |
| `/diagnostics` | robot → 5 | ulsan_gui 시스템 상태 패널 (노드 연결 판단, DEC-040) |
| `/limo_status` | robot → 5 | ulsan_gui 배터리 표시 (`limo_msgs/LimoStatus`) |
| `/camera/image/compressed` | robot → 5 | ulsan_gui 카메라 뷰 |
| `/pause`, `/resume` | 5 → robot | wego_traffic → wego_behaviour |
| `/goal_destination`, `/speak_text` | 5 → robot | wego_dispatcher → wego_behaviour/voice |
| `/abort`, `/cmd_vel` | 5 → robot | ulsan_gui (임무중단/텔레옵) |

> **제거된 브릿지**: `/tf`, `/tf_static`, `/map` — 브릿징 불필요(각 기기 로컬 데이터). 로봇↔로봇 `/amcl_pose` peer 브릿지 — FleetObstacleLayer 폐기로 제거.

### 맵 배포 절차 (domain bridge 대신 scp)

```bash
# STEP 1: LIMO 1에서 SLAM 후 맵 저장
ros2 run nav2_map_server map_saver_cli -f ~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/map

# STEP 2: LIMO 2로 복사
scp ~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/map.pgm \
    ~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/map.yaml \
    wego@192.168.0.102:~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/

# STEP 3: 노트북으로 복사 (노트북 1, 2 동일)
scp ~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/map.pgm \
    ~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/map.yaml \
    user@192.168.0.115:~/maps/
scp ~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/map.pgm \
    ~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/map.yaml \
    user@192.168.0.116:~/maps/

# STEP 4: 각 기기에서 map_server 실행 (navigation_diff_launch.py에 포함됨)
# 노트북은 별도 map_server 노드 실행 또는 관제 UI에서 직접 읽기
```

### 토픽 이름 전략

각 로봇의 `/amcl_pose`는 domain bridge 수신 측에서 구분 가능한 이름으로 remap:

| 발신 | 수신측 토픽명 | 비고 |
|------|--------------|------|
| LIMO 1 `/amcl_pose` → domain 5 | `/limo1/amcl_pose` | 관제 GUI 시각화 + wego_traffic 거리감지 |
| LIMO 2 `/amcl_pose` → domain 5 | `/limo2/amcl_pose` | 관제 GUI 시각화 + wego_traffic 거리감지 |

> wego_traffic이 domain 5에서 두 로봇 pose를 모두 받아 거리를 계산하므로, 로봇↔로봇 직접 브릿징 불필요.

---

## 네트워크 구성 권장사항

- AP(공유기)에서 로봇 2대 + 노트북에 **고정 IP** 할당 권장
- 같은 서브넷 내 통신 확인: `ping` 테스트 선행
- Wi-Fi 간섭 최소화: 5GHz 대역 사용 권장
- 실시간 주행 중 패킷 손실 모니터링 권장 (`ros2 topic hz`, `ros2 topic delay`)

---

## 통신 검증 체크리스트

```
□ 각 기기 DOMAIN_ID 확인: echo $ROS_DOMAIN_ID
  → 데스크탑=5/6/7(터미널별), LIMO 1=6, LIMO 2=7, 노트북=5

□ RMW_IMPLEMENTATION=rmw_cyclonedds_cpp 확인 (각 기기 .bashrc)
  ※ cyclone_peers.xml 삭제됨 — CYCLONEDDS_URI 설정 불필요

■ Domain Bridge 실행 후 토픽 브릿징 확인 (데스크탑 domain 5 터미널) — done (2026-04-22)
  → ros2 topic echo /limo1/amcl_pose   # LIMO 1 위치 수신 확인 ✓
  → ros2 topic echo /limo2/amcl_pose   # LIMO 2 위치 수신 확인
  ※ /map은 브릿징 없음 — 각 기기 로컬 map_server에서 발행 (DEC-012)

□ 주행 중 토픽 끊김 없는지 확인: ros2 topic hz /limo1/amcl_pose
```

---

## 트러블슈트 기록

### TS-003: domain_bridge YAML 형식 오류 — resolved (2026-04-22)

**증상**: `domain_bridge::YamlParsingError: expected map value for 'topics'`

**원인**: `topics` 하위를 sequence(리스트, `-` 형식)로 작성했으나 domain_bridge는 map 형식을 요구.
또한 같은 토픽을 두 도메인으로 브릿징할 때 map에서 중복 키 사용 불가.

**해결**:
- `topics` 하위를 map 형식으로 변경 (`topic_name:` 키 제거, 토픽명을 키로 사용)
- DEST_DOMAIN 플레이스홀더 도입 → bridge 인스턴스 2개 생성 (laptop용, peer용)

```yaml
# 올바른 형식
topics:
  /amcl_pose:
    type: geometry_msgs/msg/PoseWithCovarianceStamped
    from_domain: ROBOT_DOMAIN
    to_domain: DEST_DOMAIN
    remap: /ROBOT_NAME/amcl_pose
```

---

### TS-002: domain_bridge `--config` 플래그 미지원 — resolved (2026-04-22)

**증상**: `domain_bridge::YamlParsingError: error parsing the file '--config': file does not exist`

**원인**: `domain_bridge` 실행파일은 config 파일을 `--config file.yaml` 플래그가 아닌 positional 인자로 받음.
launch 파일에서 `arguments=['--config', tmp.name]`으로 전달해 `--config` 자체가 파일명으로 해석됨.

**해결**: `arguments=[tmp.name]`으로 수정 (플래그 제거).

---

### TS-001: RViz /map 갱신 지연 (Wi-Fi 환경 DDS 이슈) — resolved (2026-04-16)

**증상**: 외부 PC에서 RViz로 `/map`, `/scan` 시각화 시 갱신 매우 느림. 로봇 내부 PC에서는 정상.

**원인**: ROS2 기본 DDS(Fast DDS)의 multicast 기반 discovery가 Wi-Fi 환경에서 비효율적.
- AP에서 multicast 패킷 buffering/제한 발생
- `/map`은 대용량 데이터라 지연 더욱 심함
- packet loss 및 latency 증가

**해결**: Fast DDS → Cyclone DDS 변경 + unicast 기반 peer discovery 적용

```bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```

Cyclone DDS 선택 이유:
- peer 기반 unicast discovery 설정이 단순함
- 경량 구조로 latency 낮음
- Fast DDS도 unicast 가능하나 설정 복잡도 높음

**결과**: `/map` 갱신 속도 크게 개선, RViz 실시간 시각화 가능 수준으로 회복.

**교훈**: Wi-Fi 환경에서 Fast DDS 기본 멀티캐스트 discovery는 대용량 토픽(`/map`, `/pointcloud`)에서 취약 → DDS 구현체로 **Cyclone DDS 채택**(경량·저지연).

> **후속 정정 (2026-05-25)**: 이후 운용에서 **`/map`은 도메인 브릿지 없이 각 기기 로컬 map_server가 독립 발행**(DEC-012)하도록 바뀌어 대용량 토픽이 Wi-Fi를 건너지 않게 됨. 그 결과 unicast peer 설정의 필요성이 사라져 **`cyclone_peers.xml`을 폐기하고 도메인 분리(5/6/7) + Cyclone DDS 기본 멀티캐스트 auto-discovery**로 단순화함. 현재는 동일 AP 내 자동 discovery로 충분(이 문서 상단 "CycloneDDS 설정" 섹션이 정본). 즉 "unicast 필수" 교훈은 `/map` 로컬 발행 전환으로 무효화됨.
