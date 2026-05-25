// 현장 방문 — 빈 상담실 안내 페이지
//
// 마운트 즉시 GET /walkin/rooms/available 를 호출해
// 현재 시간대에 예약이 없는 상담실(우선순위 1번)을 표시한다
//
// [안내 시작] 클릭 시:
//   1. POST /walkin/assign → DB에 walk-in 행 삽입 + IDLE 로봇 임무 배정
//      → 관제 UI 알림 로그도 이 엔드포인트에서 생성
//   2. 성공: /guiding으로 이동
//   3. 실패: 에러 메시지 표시

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAvailableRoom, assignWalkin } from '../api';

const ROOM_LABELS = {
  counseling_1:           '상담실 1',
  counseling_2:           '상담실 2',
  intensive_counseling_1: '집중상담실 1',
  intensive_counseling_2: '집중상담실 2',
};

function WalkinRoomPage() {
  const navigate = useNavigate();

  const [room, setRoom]       = useState(null);   // 배정 가능 상담실 키
  const [fetching, setFetching] = useState(true); // 초기 상담실 조회 중
  const [noRoom, setNoRoom]   = useState(false);  // 모든 상담실 배정됨
  const [loading, setLoading] = useState(false);  // 안내 시작 버튼 로딩
  const [error, setError]     = useState('');

  // 마운트 시 빈 상담실 조회
  useEffect(() => {
    (async () => {
      try {
        const data = await getAvailableRoom();
        setRoom(data.room);
      } catch (err) {
        if (err.response?.status === 503) {
          // 현재 시간대 상담실 4개 모두 예약됨
          setNoRoom(true);
        } else {
          setError('상담실 조회 중 오류가 발생했습니다.');
        }
      } finally {
        setFetching(false);
      }
    })();
  }, []);

  const handleStart = async () => {
    setError('');
    setLoading(true);
    try {
      const result = await assignWalkin(room);
      navigate('/guiding', {
        state: {
          robot:       result.robot,
          destination: ROOM_LABELS[room] || room,
        },
      });
    } catch (err) {
      if (err.response?.status === 503) {
        setError('현재 안내 로봇이 모두 사용 중입니다. 잠시 후 다시 시도해주세요.');
      } else {
        setError('오류가 발생했습니다. 다시 시도해주세요.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>

      {/* 뒤로 가기 */}
      <button style={styles.backBtn} onClick={() => navigate('/walkin')}>
        ← 뒤로
      </button>

      <div style={styles.card}>

        {/* 초기 조회 중 */}
        {fetching && (
          <p style={styles.loadingText}>상담실을 확인하는 중입니다...</p>
        )}

        {/* 모든 상담실 만석 */}
        {!fetching && noRoom && (
          <>
            <div style={styles.icon}>😔</div>
            <h2 style={styles.title}>현재 빈 상담실이 없습니다</h2>
            <p style={styles.desc}>
              카운터에 문의하시거나 잠시 후 다시 시도해주세요.
            </p>
            <button style={styles.backSecondary} onClick={() => navigate('/')}>
              처음으로
            </button>
          </>
        )}

        {/* 상담실 배정 가능 */}
        {!fetching && room && (
          <>
            <div style={styles.icon}>🏢</div>
            <h2 style={styles.title}>{ROOM_LABELS[room]}으로 안내해드립니다</h2>
            <p style={styles.desc}>
              안내 로봇이 {ROOM_LABELS[room]}까지 직접 안내합니다.
              <br />로봇을 따라 이동해주세요.
            </p>

            {error && <p style={styles.error}>{error}</p>}

            <button
              onClick={handleStart}
              disabled={loading}
              style={{ ...styles.startBtn, opacity: loading ? 0.6 : 1 }}
            >
              {loading ? '배정 중...' : '안내 시작'}
            </button>
          </>
        )}

        {/* API 오류 */}
        {!fetching && error && !room && !noRoom && (
          <p style={styles.error}>{error}</p>
        )}

      </div>
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
    position: 'relative',
  },
  backBtn: {
    position: 'absolute',
    top: 24,
    left: 24,
    background: 'none',
    fontSize: 18,
    color: '#4b5563',
    padding: '8px 16px',
  },
  card: {
    background: '#ffffff',
    borderRadius: 20,
    padding: '48px 40px',
    width: '100%',
    maxWidth: 480,
    boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 20,
  },
  loadingText: {
    fontSize: 18,
    color: '#6b7280',
  },
  icon: {
    fontSize: 60,
  },
  title: {
    fontSize: 26,
    fontWeight: 700,
    color: '#1a202c',
    textAlign: 'center',
  },
  desc: {
    fontSize: 16,
    color: '#6b7280',
    textAlign: 'center',
    lineHeight: 1.7,
  },
  error: {
    fontSize: 15,
    color: '#ef4444',
    textAlign: 'center',
  },
  startBtn: {
    width: '100%',
    padding: '20px',
    fontSize: 24,
    fontWeight: 700,
    background: '#2563eb',
    color: '#ffffff',
    borderRadius: 14,
  },
  backSecondary: {
    padding: '14px 32px',
    fontSize: 18,
    fontWeight: 600,
    background: '#f3f4f6',
    color: '#374151',
    borderRadius: 12,
  },
};

export default WalkinRoomPage;
