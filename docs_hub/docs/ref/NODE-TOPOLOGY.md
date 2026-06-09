# NODE-TOPOLOGY — ROS 2 노드 및 토픽 구성

## Domain 구성

| 엔티티 | ROS_DOMAIN_ID | 역할 |
|--------|---------------|------|
| 리더 로봇 (LIMO 1) | **6** | 주 안내 로봇 |
| 서브 로봇 (LIMO 2) | **7** | 보조 안내 로봇 |
| 관제 노트북 | **5** | ulsan_gui 관제 GUI (PyQt). 보조로 wego_ui RViz 맵 모니터링 |

Domain 간 통신은 `ros2-domain-bridge`로 필요한 토픽만 선택적으로 브릿징.
→ 설정 상세: [COMMUNICATION.md](COMMUNICATION.md)

---

## 노드 목록

### wego 패키지
| 노드 | 역할 |
|------|------|
| `/robot_base_node` | 하드웨어 드라이버 |
| `/cartographer_node` | SLAM 지도 작성 (매핑 시) |
| `ekf_node` (robot_localization) | 휠 오도메트리 + IMU 융합 → `odom→base_link` TF |

### wego_2d_nav 패키지
| 노드 | 역할 |
|------|------|
| `/nav2_bringup` | Nav2 스택 (플래너, 컨트롤러, AMCL) |
| `/amcl` | 위치 추정 |

### wego_bridge 패키지 (구현 완료)
| 노드 | 역할 |
|------|------|
| `domain_bridge` | 로봇 domain(6/7) ↔ 서버 domain 5 브릿징 (단일 `bridge_robot.yaml` 템플릿, DEC-028). 로봇↔로봇 peer 브릿지 없음 |

### wego_traffic 패키지 (구현 완료, domain 5)
| 노드 | 역할 |
|------|------|
| `wego_traffic_node` | 두 로봇 `/amcl_pose` 거리 감지 → 우선순위 기반 `/pause`·`/resume` 발행 (DEC-022) |

### wego_dispatcher 패키지 (구현 완료, domain 5)
| 노드 | 역할 |
|------|------|
| `dispatcher_node` | FastAPI `missions` PENDING 0.5s 폴링 → IDLE 로봇에 `/goal_destination`(`limo_msgs/GuideGoal`: 목적지+출발멘트) 발행, 귀환 시 complete/fail 처리 (DEC-027/036/048). 출발멘트는 voice로 직접 안 보내고 GuideGoal로 behaviour 경유 |

### ulsan_gui 패키지 (구현 완료, domain 5)
| 노드 | 역할 |
|------|------|
| `ulsan_gui` | PyQt5 관제 대시보드 — 지도/로봇 상태 카드/긴급 제어/이벤트·미션 로그/시스템 상태(diagnostics, DEC-040) |

> **폐기**: `ulsan_obstacle_layer`(PeerObstacleLayer, 상대 로봇 가상 장애물 costmap 주입) — 동적 충돌 회피 구조적 한계로 삭제, 우선순위 pause/resume로 대체 (DEC-022)

### wego_behaviour 패키지 (구현 완료, 데스크탑 domain 6/7)
| 노드 | 역할 |
|------|------|
| `behaviour_node` | Yasmin FSM 실행 (IDLE / GUIDING / RETURNING / WAITING / FAILED), 임무 상태 관리. `/aruco_home_dock` 서비스 client |

### wego_aruco 패키지 (LIMO 도메인 6/7 = 로봇에서 실행, DEC-043)
| 노드 | 역할 |
|------|------|
| `aruco_home_dock` | `/aruco_home_dock` 서비스 — PBVS로 홈 정밀 정차 (staged 채택 DEC-038, polar 제거 DEC-042). 카메라→cmd_vel 닫힌 루프라 로봇 로컬 실행 (DEC-043) |
| `aruco_measure` | 마커 상대 포즈(거리·각도) 실시간 측정 도구 — `ros2 run`으로 수동 실행, target_dist 실측·튜닝용 (운영 비포함). 구 `pose_corrector` 대체 (2026-06-01) |

### ulsan_person_detect 패키지 (구현 완료, 2026-06-01)
| 노드 | 역할 |
|------|------|
| `person_detect_node` | YOLOv8n(COCO 사전학습) RGB 추론 + Depth 거리 게이팅. `/camera/color/image_raw` + `/camera/depth/image_raw` 구독 → 0.7m 이내 사람 감지 시 `/person_detected=true` 발행 (10Hz). **LIMO 도메인 6/7 = 로봇에서 실행 (DEC-043), `ros2 run` 직접 실행** |

### ulsan_bt_plugins 패키지 (구현 완료, 2026-06-01)
| 노드 | 역할 |
|------|------|
| `PersonClearCondition` | Nav2 BT 커스텀 C++ 조건 노드(plugin). `/person_detected` 구독 → 사람 없음=SUCCESS, 사람 감지=RUNNING. ReactiveSequence가 FollowPath를 halt → 정지. DEC-041 |

### wego_voice 패키지 (구현 완료, TTS 전용)
| 노드 | 역할 |
|------|------|
| `voice_node` | `/speak_text` 구독(도착·실패 비동기) + `/speak` 서비스(발화-후-응답, 출발 안내 동기화 DEC-048) → edge-tts + mpg123 (DEC-024). 데스크탑 domain 6/7. MultiThreadedExecutor+콜백그룹(발화 블로킹 중 진단 유지) |

> **폐기**: `wego_coordinator`(on_duty 결정) — 예약+`wego_dispatcher` 아키텍처로 대체 (DEC-027). 음성 인식 파이프라인(VAD/wakeword/STT/NLU `/vad_node`·`/wakeword_node`·`/stt_node`·`/nlu_node`)도 예약 시스템 도입으로 전부 폐기 (DEC-024) — 구현되지 않음.
> 사람 감지(YOLOv8)는 별도 `ulsan_person_detect` 패키지 — 위 섹션 참고.

---

## 주요 토픽

### 로봇 내부 (각 Domain 내)

| 토픽 | 타입 | 발행 | 구독 |
|------|------|------|------|
| `/amcl_pose` | `geometry_msgs/PoseWithCovarianceStamped` | amcl | wego_bridge(→5) |
| `/cmd_vel` | `geometry_msgs/Twist` | nav2 controller / aruco_home_dock | robot_base |
| `/scan` | `sensor_msgs/LaserScan` | LiDAR 드라이버 | cartographer, nav2 |
| `/goal_destination` | `limo_msgs/GuideGoal` | wego_dispatcher (5→) | wego_behaviour |
| `/robot_status` | `std_msgs/String` | wego_behaviour | wego_bridge(→5) |
| `/speak_text` | `std_msgs/String` | wego_behaviour (도착·실패, 동일 도메인) | wego_voice voice_node |
| `/speak` | `limo_msgs/Speak` (서비스) | wego_behaviour (client) | wego_voice (server) — 출발멘트 발화-후-응답 (DEC-048) |
| `/pause`·`/resume` | `std_msgs/Empty` | wego_traffic (5→) | wego_behaviour |
| `/abort`·`/recover` | `std_msgs/Empty` | ulsan_gui (5→) | wego_behaviour |
| `/person_detected` | `std_msgs/Bool` | person_detect_node | PersonClearCondition (Nav2 BT), wego_bridge(→5 GUI liveness) |
| `/aruco_home_dock` | `std_srvs/Trigger` (서비스) | wego_behaviour (client) | aruco_home_dock (server) |
| `/initialpose` | `geometry_msgs/PoseWithCovarianceStamped` | aruco_home_dock | amcl |

### 로봇 간 (Domain Bridge 경유)

| 토픽 | 방향 | 용도 |
|------|------|------|
| `/limo1/amcl_pose`, `/limo2/amcl_pose` | 로봇 → 서버(5) | wego_traffic 거리감지 + ulsan_gui 위치 마커 |
| `/limo{1,2}/robot_status` | 로봇 → 서버(5) | wego_traffic, wego_dispatcher |
| `/limo{1,2}/diagnostics`, `/limo_status`, `/person_detected` | 로봇 → 서버(5) | ulsan_gui 연결/준비 판정(DEC-047)·배터리·사람감지 liveness |
| `/limo{1,2}/goal_destination` (`GuideGoal`) | 서버(5) → 로봇 | wego_dispatcher 임무 배정(목적지+출발멘트). ※ 출발멘트 `/speak_text` 라우트는 폐지(DEC-048) |
| `/limo{1,2}/pause`, `/resume` | 서버(5) → 로봇 | wego_traffic 충돌 회피 |
| `/limo{1,2}/abort`, `/recover`, `/cmd_vel` | 서버(5) → 로봇 | ulsan_gui 임무중단/복구완료/텔레옵 |

> 로봇↔로봇 직접 브릿지는 없음 (PeerObstacleLayer 폐기). wego_traffic이 domain 5에서 두 pose를 받아 거리 계산.

> 브릿지 설정 상세: [COMMUNICATION.md](COMMUNICATION.md)

---

## TF 프레임 구성 (DEC-011 확정)

각 로봇은 **표준 TF 프레임**을 그대로 사용. prefix 없음 (DEC-011에서 폐기).
각 로봇이 서로 다른 domain(6, 7)에서 동작하므로 TF 충돌 없음.
노트북(domain 5)에는 `/tf` 브릿징 없음 — `/amcl_pose`만 수신.

```
map → odom → base_link → laser
                       → camera_mount → camera_rotate → camera_link ...
```

### TF 발행 노드 (teleop_launch.py 실행 시)

| 프레임 체인 | 발행 노드 |
|------------|---------|
| `odom → base_link` | EKF (`ekf_node`) |
| `base_link → laser` 등 | robot_state_publisher |
| `map → odom` | AMCL (navigation_diff_launch.py) |
