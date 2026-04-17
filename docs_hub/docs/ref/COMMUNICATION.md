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

| 기기 | DOMAIN_ID |
|------|-----------|
| 노트북 (관제) | **5** |
| LIMO 1 (리더) | **6** |
| LIMO 2 (서브) | **7** |

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
각 로봇이 자신의 토픽을 domain 5(노트북)로 push하는 방식.

### 실행 방법

```bash
# 각 LIMO에서 (ROS_DOMAIN_ID는 bashrc에서 자동 읽음)
ros2 launch wego_fleet robot_bridge_launch.py             # 일반 로봇
ros2 launch wego_fleet robot_bridge_launch.py leader:=true  # 리더 로봇 (/map 추가 전송)
```

### 설계 (DEC-010)

- **단일 템플릿**: `wego_fleet/config/domain_bridge_robot.yaml` — `ROBOT_DOMAIN` 플레이스홀더
- **launch**: `robot_bridge_launch.py`가 `ROS_DOMAIN_ID` 환경변수로 `from_domain` 자동 결정
- **`/map`**: `leader:=true` 인 로봇만 전송 (두 로봇이 동일한 맵 사용)

### 브릿지 토픽 (현재 단계)

| 토픽 | 방향 | 조건 |
|------|------|------|
| `/tf` | robot domain → 5 | 항상 |
| `/tf_static` | robot domain → 5 | 항상 |
| `/map` | robot domain → 5 | `leader:=true` 인 로봇만 |

> 추후 추가 예정: `/amcl_pose` (fleet obstacle layer), 카메라 압축 이미지 (관제 UI)

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

□ cyclonedds_peers.xml에 실제 IP 주소 입력 (미완료)
□ 각 기기에서 CYCLONEDDS_URI 환경변수 설정 확인

□ Domain Bridge 실행 후 토픽 브릿징 확인 (노트북에서)
  → ros2 topic echo /robot1/amcl_pose   # LIMO 1 위치 수신 확인
  → ros2 topic echo /robot2/amcl_pose   # LIMO 2 위치 수신 확인
  → ros2 topic echo /map                # 맵 수신 확인
  → ros2 topic echo /tf                 # TF 수신 확인

□ 주행 중 토픽 끊김 없는지 확인: ros2 topic hz /tf
```

---

## 트러블슈트 기록

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
