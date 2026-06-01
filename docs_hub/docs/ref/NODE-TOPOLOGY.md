# NODE-TOPOLOGY — ROS 2 노드 및 토픽 구성

## Domain 구성

| 엔티티 | ROS_DOMAIN_ID | 역할 |
|--------|---------------|------|
| 리더 로봇 (LIMO 1) | **6** | 주 안내 로봇 |
| 서브 로봇 (LIMO 2) | **7** | 보조 안내 로봇 |
| 관제 노트북 | **5** | RViz 모니터링 |

Domain 간 통신은 `ros2-domain-bridge`로 필요한 토픽만 선택적으로 브릿징.
→ 설정 상세: [COMMUNICATION.md](COMMUNICATION.md)

---

## 노드 목록 (예정)

### wego 패키지 (기존)
| 노드 | 역할 |
|------|------|
| `/robot_base_node` | 하드웨어 드라이버 |
| `/cartographer_node` | SLAM 지도 작성 |

### wego_2d_nav 패키지 (기존)
| 노드 | 역할 |
|------|------|
| `/nav2_bringup` | Nav2 스택 (플래너, 컨트롤러, AMCL) |
| `/amcl` | 위치 추정 |

### wego_bridge 패키지 (구현 완료)
| 노드 | 역할 |
|------|------|
| `domain_bridge` | `/amcl_pose` → 노트북·상대 로봇 domain으로 브릿징 |

### ulsan_obstacle_layer 패키지 (구현 완료)
| 노드 | 역할 |
|------|------|
| `PeerObstacleLayer` | 상대 로봇 `/amcl_pose` → global costmap LETHAL_OBSTACLE 주입 (Nav2 플러그인) |

### wego_behaviour 패키지 (뼈대 완료)
| 노드 | 역할 |
|------|------|
| `wego_behaviour` | Yasmin FSM 실행 (IDLE / GUIDING / RETURNING / WAITING), 임무 상태 관리 |

### wego_aruco 패키지
| 노드 | 역할 |
|------|------|
| `aruco_pose_corrector` | 주행 중 마커 감지 → `/initialpose` 발행 (passive AMCL 보정) |
| `aruco_home_dock` | `/aruco_home_dock` 서비스 — IBVS로 홈 정밀 정차 (DEC-029) |

### ulsan_person_detect 패키지 (구현 완료, 2026-06-01)
| 노드 | 역할 |
|------|------|
| `person_detect_node` | YOLOv8n(COCO 사전학습) RGB 추론 + Depth 거리 게이팅. `/camera/color/image_raw` + `/camera/depth/image_raw` 구독 → 0.7m 이내 사람 감지 시 `/person_detected=true` 발행 (10Hz). 데스크탑 domain 6/7 |

### ulsan_bt_plugins 패키지 (구현 완료, 2026-06-01)
| 노드 | 역할 |
|------|------|
| `PersonClearCondition` | Nav2 BT 커스텀 C++ 조건 노드(plugin). `/person_detected` 구독 → 사람 없음=SUCCESS, 사람 감지=RUNNING. ReactiveSequence가 FollowPath를 halt → 정지. DEC-041 |

### wego_coordinator 패키지 (미구현)
| 노드 | 역할 |
|------|------|
| `wego_coordinator` | 각 로봇 status 구독 → on_duty 결정·발행 (노트북 전용) |

### wego_voice 패키지 (신규)
| 노드 | 역할 |
|------|------|
| `/vad_node` | Silero VAD: 마이크 → 사람 목소리 필터 |
| `/wakeword_node` | openWakeWord: "헤이 리모" 감지 |
| `/stt_node` | faster-whisper (CUDA): 음성 → 텍스트 |
| `/nlu_node` | If-else / Gemini API / Gemma-2B 의도 해석 |
| `/tts_node` | Piper: 텍스트 → 음성 출력 |

> 사람 감지(YOLOv8)는 별도 `ulsan_person_detect` 패키지로 분리 구현 — 위 섹션 참고.

---

## 주요 토픽

### 로봇 내부 (각 Domain 내)

| 토픽 | 타입 | 발행 | 구독 |
|------|------|------|------|
| `/amcl_pose` | `geometry_msgs/PoseWithCovarianceStamped` | amcl | PeerObstacleLayer, wego_bridge |
| `/cmd_vel` | `geometry_msgs/Twist` | nav2 controller | robot_base |
| `/scan` | `sensor_msgs/LaserScan` | LiDAR 드라이버 | cartographer, nav2 |
| `/on_duty` | `std_msgs/Bool` | wego_coordinator (노트북) | wego_behaviour |
| `/robot_status` | `std_msgs/String` | wego_behaviour | wego_coordinator (bridge 경유) |
| `/goal_destination` | `std_msgs/String` | wego_voice (NLU 결과) | wego_behaviour |
| `/voice/vad_active` | `std_msgs/Bool` | vad_node | wakeword_node |
| `/voice/wakeword_detected` | `std_msgs/Bool` | wakeword_node | wego_behaviour |
| `/voice/stt_result` | `std_msgs/String` | stt_node | nlu_node |
| `/voice/nlu_intent` | `std_msgs/String` | nlu_node | wego_behaviour |
| `/voice/tts_request` | `std_msgs/String` | wego_behaviour | tts_node |
| `/person_detected` | `std_msgs/Bool` | person_detect_node | PersonClearCondition (Nav2 BT) |

### 로봇 간 (Domain Bridge 경유)

| 토픽 | 방향 | 용도 |
|------|------|------|
| `/limo_1/amcl_pose` | LIMO1(6) → LIMO2(7) | LIMO2 PeerObstacleLayer 입력 |
| `/limo_2/amcl_pose` | LIMO2(7) → LIMO1(6) | LIMO1 PeerObstacleLayer 입력 |
| `/limo_1/amcl_pose` | LIMO1(6) → 노트북(5) | 관제 UI 위치 마커 |
| `/limo_2/amcl_pose` | LIMO2(7) → 노트북(5) | 관제 UI 위치 마커 |
| `/limo_1/robot_status` | LIMO1(6) → 노트북(5) | wego_coordinator on_duty 결정 |
| `/limo_2/robot_status` | LIMO2(7) → 노트북(5) | wego_coordinator on_duty 결정 |
| `/limo_1/on_duty` | 노트북(5) → LIMO1(6) | wego_behaviour FSM 활성화 여부 |
| `/limo_2/on_duty` | 노트북(5) → LIMO2(7) | wego_behaviour FSM 활성화 여부 |

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
