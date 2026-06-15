// 안내 대기 화면 — 모든 로봇이 안내 중일 때(큐 진입) 표시
//
// CheckinResultPage / WalkinRoomPage / ClassroomPage에서 임무 생성 응답이
// queued=true일 때 이동한다. 임무는 이미 PENDING으로 생성돼 대기열에 있고,
// 로봇이 복귀하면 wego_dispatcher가 FIFO(먼저 온 순서)로 꺼내 배정한다.
//
// 이 화면은 폴링하지 않는다 — 방문자는 좌측 의자에서 대기하고, 로봇이
// 복귀해 발화(예약자는 성함 호명)하면 따라간다. 화면은 잠시 후 홈으로 복귀해
// 키오스크를 다음 방문자에게 양보한다.

import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

const REDIRECT_DELAY_MS = 7000;   // 안내문 표시 후 홈 복귀까지

function WaitingPage() {
  const navigate  = useNavigate();
  const { state } = useLocation();
  const destination = state?.destination;

  useEffect(() => {
    const t = setTimeout(() => navigate('/'), REDIRECT_DELAY_MS);
    return () => clearTimeout(t);
  }, [navigate]);

  return (
    <div style={styles.container}>
      <div style={styles.icon}>🪑</div>
      <h2 style={styles.title}>현재 모든 안내 로봇들이 안내중입니다</h2>
      <p style={styles.desc}>
        좌측 의자에서 대기하시면
        <br />가장 빠른 로봇이 안내해드리겠습니다.
      </p>
      {destination && <p style={styles.destination}>{destination}</p>}
      <p style={styles.subText}>잠시 후 처음 화면으로 돌아갑니다</p>
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
  icon: {
    fontSize: 72,
    marginBottom: 8,
  },
  title: {
    fontSize: 28,
    fontWeight: 700,
    color: '#1a202c',
  },
  desc: {
    fontSize: 20,
    color: '#374151',
    lineHeight: 1.7,
  },
  // 안내 목적지 강조 (대기 중 본인 목적지 상기용)
  destination: {
    fontSize: 24,
    fontWeight: 700,
    color: '#2563eb',
  },
  subText: {
    fontSize: 16,
    color: '#9ca3af',
    marginTop: 8,
  },
};

export default WaitingPage;
