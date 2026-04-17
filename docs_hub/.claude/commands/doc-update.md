# /doc-update

코드 변경 후 관련 문서를 갱신한다.

## Change Class → 필수 갱신 문서

| 변경 영역 | 필수 갱신 | 조건부 갱신 |
|-----------|----------|-----------|
| 어떤 코드든 | `docs/status/PROJECT-STATUS.md` | — |
| ROS 노드/토픽 추가·변경 | `docs/ref/NODE-TOPOLOGY.md` | `docs/ref/ARCHITECTURE.md` |
| 음성 파이프라인 로직 | `docs/ref/VOICE-PIPELINE.md` | `docs/ref/ARCHITECTURE.md` |
| Nav2 / SLAM / waypoints | `docs/ref/NAVIGATION.md` | `docs/ref/ARCHITECTURE.md` |
| CycloneDDS / Domain Bridge 설정 | `docs/ref/COMMUNICATION.md` | `docs/ref/NODE-TOPOLOGY.md` |
| 메시지 타입 (.msg/.srv) | `docs/ref/NODE-TOPOLOGY.md` | `docs/ref/ARCHITECTURE.md` |
| 행동 트리 구조 | `docs/ref/ARCHITECTURE.md` | — |
| launch 파일 | `docs/ref/NODE-TOPOLOGY.md` | `docs/ref/COMMUNICATION.md` |
| 경계 결정 | `docs/status/DECISION-LOG.md` | → resolved 시 archive 이동 |

## 프로세스

1. `git diff --name-only` 로 변경 파일 목록 수집
2. 위 테이블에서 변경 영역 분류
3. 필수 문서를 실제 수정 (최소 변경, 정본 1곳 원칙)
4. `DECISION-LOG.md`: pending → resolved 시 `archive/decisions-resolved.md`로 이동
5. `PROJECT-STATUS.md`: 완료 항목에 날짜 포함 확인 (`done (YYYY-MM-DD)`)
6. trivial 변경(주석, 오탈자, 테스트만)이면 "문서 갱신 불필요"로 종료
7. 갱신 보고: 수정된 문서 목록 출력

## 규칙
- 같은 사실을 여러 문서에 반복하지 않음 — 링크로 참조
- 구현과 문서 충돌 시: 구현 우선 → 문서를 맞춤
- done 항목에 날짜 없으면 날짜 추가
