// 안내 중 화면 — 로봇 귀환 감지 후 완료 표시
//
// CheckinResultPage / WalkinRoomPage / ClassroomPage에서 로봇 배정 성공 시 이동한다
// React Router state로 받는 값:
//   robot       : "limo1" | "limo2"    — 배정된 로봇
//   destination : "상담실 1" 등 표시명 — 화면에 목적지 표시용
//
// 동작 흐름:
//   1. 2초 후부터 GET /robots/status 폴링 시작 (0.5초 간격)
//      → 초기 2초 대기: 로봇이 BUSY로 전환되기 전에 IDLE로 오감지하는 것을 방지
//   2. 로봇이 BUSY/RETURNING → IDLE로 전환되면 '완료' 상태로 전환
//   3. 완료 후 4초 뒤 홈으로 자동 이동
//   4. 폴링 10분 타임아웃: 네트워크 이상 등 예외 상황 대비

import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { getRobotStatus } from '../api';

// 로봇이 IDLE로 복귀를 감지하기 위한 상태 머신
// waiting_start → 로봇이 처음 IDLE에서 BUSY로 바뀔 때까지 대기
// waiting_idle  → 로봇이 BUSY/RETURNING 상태에서 다시 IDLE로 바뀔 때까지 대기
// completed     → 홈 복귀 완료
const PHASE = { WAITING_START: 'waiting_start', WAITING_IDLE: 'waiting_idle', COMPLETED: 'completed' };

const POLL_INTERVAL_MS = 500;   // 폴링 간격 0.5초
const INIT_DELAY_MS    = 2000;  // 폴링 시작 전 초기 대기 (BUSY 전환 여유)
const TIMEOUT_MS       = 600000; // 10분 타임아웃 (로봇 미복귀 대비)
const REDIRECT_DELAY_MS = 4000; // 완료 후 홈 이동까지 대기

function GuidingPage() {
  const navigate  = useNavigate();
  const { state } = useLocation();

  // React Rules of Hooks: 훅은 조건문 앞에 무조건 호출해야 한다
  // 비정상 접근 시에도 훅을 먼저 호출한 뒤 useEffect 안에서 리다이렉트
  const [phase, setPhase]       = useState(PHASE.WAITING_START);
  const [timedOut, setTimedOut] = useState(false);
  const pollRef                 = useRef(null);
  const timeoutRef              = useRef(null);

  const robot       = state?.robot;
  const destination = state?.destination;

  useEffect(() => {
    // 비정상 접근(state 없음) 방어 — 훅 호출 후 여기서 처리
    if (!robot) {
      navigate('/');
      return;
    }
    let currentPhase = PHASE.WAITING_START;

    const startPolling = () => {
      pollRef.current = setInterval(async () => {
        try {
          const status = await getRobotStatus();
          const robotState = status[robot]; // "IDLE" | "BUSY" | "RETURNING" | "WAITING"

          if (currentPhase === PHASE.WAITING_START) {
            // 로봇이 IDLE에서 벗어나면(임무 수락) 본격 대기 시작
            if (robotState !== 'IDLE') {
              currentPhase = PHASE.WAITING_IDLE;
              setPhase(PHASE.WAITING_IDLE);
            }
          } else if (currentPhase === PHASE.WAITING_IDLE) {
            // 로봇이 임무 완료 후 홈으로 복귀해 IDLE이 되면 완료
            if (robotState === 'IDLE') {
              currentPhase = PHASE.COMPLETED;
              setPhase(PHASE.COMPLETED);
              cleanup();
              // 완료 화면을 잠시 보여준 뒤 홈으로 이동
              setTimeout(() => navigate('/'), REDIRECT_DELAY_MS);
            }
          }
        } catch {
          // 폴링 실패는 무시하고 계속 시도 (일시적 네트워크 오류 허용)
        }
      }, POLL_INTERVAL_MS);
    };

    const cleanup = () => {
      clearInterval(pollRef.current);
      clearTimeout(timeoutRef.current);
    };

    // 초기 대기 후 폴링 시작
    const initTimer = setTimeout(startPolling, INIT_DELAY_MS);

    // 전체 타임아웃: 10분 경과 시 폴링 중단 후 홈으로
    timeoutRef.current = setTimeout(() => {
      cleanup();
      setTimedOut(true);
      setTimeout(() => navigate('/'), 3000);
    }, TIMEOUT_MS);

    return () => {
      clearTimeout(initTimer);
      cleanup();
    };
  }, [robot, navigate]);

  // ── 렌더링 ──────────────────────────────────────────────────────────────

  // 비정상 접근 시 빈 화면 (useEffect에서 리다이렉트 처리)
  if (!robot) return null;

  // 타임아웃 (10분 초과)
  if (timedOut) {
    return (
      <div style={styles.container}>
        <p style={styles.subText}>시간이 초과되었습니다. 처음 화면으로 이동합니다.</p>
      </div>
    );
  }

  // 안내 완료 — 로봇 홈 복귀 확인
  if (phase === PHASE.COMPLETED) {
    return (
      <div style={styles.container}>
        <div style={styles.completeIcon}>✅</div>
        <h2 style={styles.title}>안내가 완료되었습니다</h2>
        <p style={styles.subText}>잠시 후 처음 화면으로 이동합니다</p>
      </div>
    );
  }

  // 안내 중 — 로봇 이동 중 스피너 표시
  return (
    <div style={styles.container}>
      <div className="spinner" />
      <h2 style={styles.title}>안내 로봇이 이동 중입니다</h2>
      <p style={styles.destination}>{destination}</p>
      <p style={styles.subText}>로봇을 따라 이동해주세요</p>
      <p style={styles.robotLabel}>
        {robot === 'limo1' ? 'LIMO 1호' : 'LIMO 2호'} 배정됨
      </p>
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
