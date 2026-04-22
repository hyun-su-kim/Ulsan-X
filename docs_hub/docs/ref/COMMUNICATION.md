# COMMUNICATION — CycloneDDS & Domain Bridge 설정

## 선택 배경

| 항목 | 선택 | 이유 |
|------|------|------|
| DDS 구현체 | CycloneDDS | 소규모 Wi-Fi 환경에 최적화, 안정성 검증됨 |
| 통신 방식 | 유니캐스트 | 학원 내 소규모 네트워크, 멀티캐스트 불필요 |
| Domain 분리 | ros2-domain-bridge | 필요한 토픽만 선택적 브릿징, 트래픽 최소화 |

---

## CycloneDDS 유니캐스트 설정

`cyclonedds_peers.xml` 위치: `/home/wego/Ulsan-X/cyclone_peers.xml` (이미 존재)

```xml
<!-- cyclonedds_peers.xml 기본 구조 -->
<?xml version="1.0" encoding="UTF-8"?>
<CycloneDDS>
  <Domain>
    <General>
      <Interfaces>
        <NetworkInterface name="wlan0" multicast="false"/>
      </Interfaces>
      <AllowMulticast>none</AllowMulticast>
    </General>
    <Discovery>
      <Peers>
        <!-- 리더 로봇 IP -->
        <Peer address="192.168.X.X"/>
        <!-- 서브 로봇 IP -->
        <Peer address="192.168.X.X"/>
        <!-- 서버 노트북 IP -->
        <Peer address="192.168.X.X"/>
      </Peers>
    </Discovery>
  </Domain>
</CycloneDDS>
```

> 실제 IP 주소는 네트워크 환경에 맞게 채워야 함. 각 기기의 `/etc/hosts` 또는 고정 IP 권장.

**환경변수 설정** (각 기기 `.bashrc` 또는 launch 파일):
```bash
export CYCLONEDDS_URI=file:///home/wego/Ulsan-X/cyclone_peers.xml
```

---

## Domain ID 설정 (확정)

| 기기 | IP | DOMAIN_ID | 비고 |
|------|----|-----------|------|
| 노트북 1 (관제) | 192.168.0.115 | **5** | 개발자 1 |
| 노트북 2 (관제) | 192.168.0.116 | **5** | 개발자 2 (기능 동일) |
| LIMO 1 | 192.168.0.100 | **6** | |
| LIMO 2 | 192.168.0.101 | **7** | |

> 노트북 2대는 동일한 관제 UI 역할. 개발자가 2명이라 2대이며 기능·설정 동일.

```bash
# 노트북 ~/.bashrc
export ROS_DOMAIN_ID=5

# LIMO 1 ~/.bashrc
export ROS_DOMAIN_ID=6

# LIMO 2 ~/.bashrc
export ROS_DOMAIN_ID=7
```

---

## ros2-domain-bridge 설정

**각 LIMO 로봇에서 실행** (노트북에 워크스페이스 없음 — DEC-010 참고).
각 로봇이 자신의 토픽을 필요한 domain으로 push하는 방식.

### 실행 방법

```bash
# 각 LIMO에서 동일한 명령 (leader 구분 없음 — DEC-012)
ros2 launch wego_bridge robot_bridge_launch.py
```

### 설계 (DEC-010, DEC-011, DEC-012)

- **단일 템플릿**: `wego_bridge/config/domain_bridge_robot.yaml` — `ROBOT_DOMAIN`, `PEER_DOMAIN` 플레이스홀더
- **launch**: `robot_bridge_launch.py`가 `ROS_DOMAIN_ID`, `PEER_DOMAIN_ID` 환경변수로 자동 결정
- **`/map`**: 브릿징 없음. 각 기기가 로컬 map_server로 독립 발행 (DEC-012)
- **`/amcl_pose`**: 모든 로봇이 domain 5(노트북)와 상대 로봇 domain으로 전송

### 브릿지 토픽

| 토픽 | 방향 | 목적 |
|------|------|------|
| `/amcl_pose` | robot domain → 5 | 관제 UI 위치 마커 표시 |
| `/amcl_pose` | robot domain → peer domain | 상대 로봇 FleetObstacleLayer 입력 |

> **제거된 브릿지**: `/tf`, `/tf_static`, `/map` — 모두 브릿징 불필요. 각 기기가 로컬 데이터 사용.

### 맵 배포 절차 (domain bridge 대신 scp)

```bash
# STEP 1: LIMO 1에서 SLAM 후 맵 저장
ros2 run nav2_map_server map_saver_cli -f ~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/map

# STEP 2: LIMO 2로 복사
scp ~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/map.pgm \
    ~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/map.yaml \
    wego@192.168.0.101:~/Ulsan-X/ulsan_ws/src/wego_2d_nav/maps/

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
| LIMO 1 `/amcl_pose` → domain 5 | `/limo_1/amcl_pose` | 노트북 시각화용 |
| LIMO 1 `/amcl_pose` → domain 7 | `/limo_1/amcl_pose` | LIMO 2 FleetObstacleLayer 입력 |
| LIMO 2 `/amcl_pose` → domain 5 | `/limo_2/amcl_pose` | 노트북 시각화용 |
| LIMO 2 `/amcl_pose` → domain 6 | `/limo_2/amcl_pose` | LIMO 1 FleetObstacleLayer 입력 |

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
  → 노트북=5, LIMO 1=6, LIMO 2=7

□ cyclonedds_peers.xml에 실제 IP 주소 입력 — done (LIMO1=192.168.0.100, LIMO2=192.168.0.101, 노트북1=192.168.0.115, 노트북2=192.168.0.116)
□ 각 기기에서 CYCLONEDDS_URI 환경변수 설정 확인

■ Domain Bridge 실행 후 토픽 브릿징 확인 (노트북에서) — done (2026-04-22)
  → ros2 topic echo /limo_1/amcl_pose   # LIMO 1 위치 수신 확인 ✓
  → ros2 topic echo /limo_2/amcl_pose   # LIMO 2 위치 수신 확인 (미실시)
  ※ /map은 브릿징 없음 — 각 기기 로컬 map_server에서 발행 (DEC-012)

□ 로봇 간 amcl_pose 수신 확인 (각 LIMO에서)
  → LIMO 1: ros2 topic echo /limo_2/amcl_pose
  → LIMO 2: ros2 topic echo /limo_1/amcl_pose

□ 주행 중 토픽 끊김 없는지 확인: ros2 topic hz /limo_1/amcl_pose
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

**교훈**: Wi-Fi 환경에서는 DDS multicast 대신 unicast peer 설정 필수. 대용량 토픽(`/map`, `/pointcloud`)일수록 효과 큼.
