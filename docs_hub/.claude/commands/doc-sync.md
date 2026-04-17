# /doc-sync

문서 상태를 점검한다. 수정은 하지 않음 — 갱신이 필요하면 /doc-update를 사용.

## 점검 항목

1. `git diff --name-only` → 변경 파일 분류
2. Change Class 매핑 테이블로 누락 문서 체크
3. `PROJECT-STATUS.md` 점검:
   - done 항목에 날짜 없는 것
   - 14일 이상 된 done 항목 (정리 후보)
   - in progress 항목이 실제 현재 작업인지
4. `DECISION-LOG.md` 점검:
   - 오래된 pending 결정 (30일 이상)
   - resolved 됐지만 archive 이동 안 된 항목
5. 판정 출력:
   - `✅ all docs in sync` — 갱신 불필요
   - `⚠️ N doc(s) need update` — 누락 문서 목록 출력
