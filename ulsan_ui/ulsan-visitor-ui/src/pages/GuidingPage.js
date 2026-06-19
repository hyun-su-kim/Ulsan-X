// 안내 중 화면 — 임무 상태 폴링으로 "로봇 배정"까지만 감지한다
//
// CheckinResultPage / WalkinRoomPage / ClassroomPage에서 임무 생성 성공 시 이동한다
// React Router state로 받는 값:
//   missionId   : number               — 생성된 임무 id
//   destination : "상담실 1" 등 표시명 — 화면에 목적지 표시용
//
// 동작 흐름 (배정 시점에 키오스크를 다음 방문자에게 양보):
//   1. GET /assign/{missionId} 폴링 (0.5초 간격)
//   2. PENDING → "로봇 배정 중" (ulsan_dispatcher가 로봇 선택 전)
//      ACTIVE  → 로봇 배정 완료. "로봇을 따라 이동하세요" 안내를 잠깐 보여준 뒤
//                홈으로 자동 복귀 → 두 번째 방문자가 곧바로 조회 가능
//   ※ 이후 안내·홈복귀(COMPLETED)는 로봇이 담당하므로 화면은 기다리지 않는다.
//   3. 배정 대기 타임아웃: 로봇 미배정 등 예외 상황 대비

import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { getMission } from '../api';

const POLL_INTERVAL_MS  = 500;    // 폴링 간격 0.5초
const TIMEOUT_MS        = 120000; // 2분 타임아웃 (로봇 미배정 대비)
const REDIRECT_DELAY_MS = 4000;   // 배정 안내 표시 후 홈 이동까지 대기

function GuidingPage() {
  const navigate  = useNavigate();
  const { state } = useLocation();

  // React Rules of Hooks: 훅은 조건문 앞에 무조건 호출해야 한다
  // 비정상 접근 시에도 훅을 먼저 호출한 뒤 useEffect 안에서 리다이렉트
  const [mission, setMission]   = useState({ status: 'PENDING', robot_assigned: null });
  const [timedOut, setTimedOut] = useState(false);
  const pollRef                 = useRef(null);
  const timeoutRef              = useRef(null);

  const missionId   = state?.missionId;
  const destination = state?.destination;

  useEffect(() => {
    // 비정상 접근(state 없음) 방어 — 훅 호출 후 여기서 처리
    if (!missionId) {
      navigate('/');
      return;
    }

    const cleanup = () => {
      clearInterval(pollRef.current);
      clearTimeout(timeoutRef.current);
    };

    pollRef.current = setInterval(async () => {
      try {
        const m = await getMission(missionId);
        setMission(m);
        // PENDING이 아니게 되는 순간 = 로봇 배정 완료(ACTIVE) 또는 즉시 종료(COMPLETED).
        // 배정 안내를 잠깐 보여준 뒤 홈으로 복귀해 키오스크를 다음 방문자에게 양보한다.
        if (m.status !== 'PENDING') {
          cleanup();
          setTimeout(() => navigate('/'), REDIRECT_DELAY_MS);
        }
      } catch {
        // 폴링 실패는 무시하고 계속 시도 (일시적 네트워크 오류 허용)
      }
    }, POLL_INTERVAL_MS);

    // 배정 대기 타임아웃: 2분 내 로봇 미배정 시 폴링 중단 후 홈으로
    timeoutRef.current = setTimeout(() => {
      cleanup();
      setTimedOut(true);
      setTimeout(() => navigate('/'), 3000);
    }, TIMEOUT_MS);

    return cleanup;
  }, [missionId, navigate]);

  // ── 렌더링 ──────────────────────────────────────────────────────────────

  // 비정상 접근 시 빈 화면 (useEffect에서 리다이렉트 처리)
  if (!missionId) return null;

  // 타임아웃 (10분 초과)
  if (timedOut) {
    return (
      <div style={styles.container}>
        <p style={styles.subText}>시간이 초과되었습니다. 처음 화면으로 이동합니다.</p>
      </div>
    );
  }

  // 로봇 배정 완료 — ACTIVE(또는 즉시 COMPLETED). "로봇을 따라가세요" 안내 후 홈 복귀
  const robot = mission.robot_assigned;
  if (mission.status !== 'PENDING') {
    const robotName = robot === 'limo1' ? 'LIMO 1호' : robot === 'limo2' ? 'LIMO 2호' : '안내 로봇';
    return (
      <div style={styles.container}>
        <div style={styles.completeIcon}>🤖</div>
        <h2 style={styles.title}>{robotName}가 배정되었습니다</h2>
        <p style={styles.destination}>{destination}</p>
        <p style={styles.subText}>로봇을 따라 이동해주세요</p>
        <p style={styles.subText}>잠시 후 처음 화면으로 돌아갑니다</p>
      </div>
    );
  }

  // PENDING — 로봇 배정 대기 스피너
  return (
    <div style={styles.container}>
      <div className="spinner" />
      <h2 style={styles.title}>안내 로봇을 배정하고 있습니다</h2>
      <p style={styles.destination}>{destination}</p>
      <p style={styles.subText}>잠시만 기다려주세요</p>
      <p style={styles.robotLabel}>로봇 배정 중…</p>
    </div>
  );
}

const styles = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '40px 32px',
    gap: 16,
    textAlign: 'center',
  },
  completeIcon: {
    fontSize: 80,
    marginBottom: 8,
  },
  title: {
    fontSize: 30,
    fontWeight: 700,
    color: '#1a202c',
  },
  // 목적지명 강조 표시
  destination: {
    fontSize: 28,
    fontWeight: 700,
    color: '#2563eb',
  },
  subText: {
    fontSize: 18,
    color: '#6b7280',
  },
  robotLabel: {
    fontSize: 14,
    color: '#9ca3af',
    marginTop: 8,
  },
};

export default GuidingPage;
