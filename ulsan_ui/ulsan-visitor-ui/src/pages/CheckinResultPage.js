// 예약 확인 결과 페이지
//
// CheckinPage에서 예약 조회 성공 시 이동한다
// 예약 정보(이름, 시간, 상담실)를 표시하고 안내 시작 버튼을 제공한다
//
// [안내 시작] 클릭 시:
//   1. POST /assign → 임무(PENDING) 생성. 로봇 배정은 ulsan_dispatcher 담당
//   2. queued=false (로봇 가용): /guiding으로 이동 (배정 폴링)
//   3. queued=true  (로봇 만차): /waiting으로 이동 (대기 안내 후 홈 복귀)

import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { assignReservation } from '../api';

// DB 상담실 키 → 표시명 매핑 (waypoints.yaml label과 동일)
const ROOM_LABELS = {
  counseling_1:           '상담실 1',
  counseling_2:           '상담실 2',
  intensive_counseling_1: '집중상담실 1',
  intensive_counseling_2: '집중상담실 2',
};

function CheckinResultPage() {
  const navigate  = useNavigate();
  const { state } = useLocation();

  // CheckinPage가 navigate할 때 state를 넘기지 않은 비정상 접근 방어
  // 훅은 조건문 앞에 무조건 호출 (Rules of Hooks)
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const reservation = state?.reservation;
  const roomLabel   = reservation ? (ROOM_LABELS[reservation.room] || reservation.room) : '';

  // 비정상 접근 방어 — 훅 호출 후 처리
  if (!reservation) {
    navigate('/checkin');
    return null;
  }

  const handleStart = async () => {
    setError('');
    setLoading(true);
    try {
      const result = await assignReservation(reservation.id);
      if (result.queued) {
        // 로봇 만차 → 대기열 진입. 대기 안내 화면으로 (잠시 후 홈 복귀)
        navigate('/waiting', { state: { destination: roomLabel } });
      } else {
        // 로봇 가용 → 배정 폴링 화면으로 (배정 로봇은 GuidingPage가 확인)
        navigate('/guiding', {
          state: {
            missionId:   result.mission_id,
            destination: roomLabel,
          },
        });
      }
    } catch (err) {
      setError('오류가 발생했습니다. 다시 시도해주세요.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>

      {/* 뒤로 가기 */}
      <button style={styles.backBtn} onClick={() => navigate('/checkin')}>
        ← 뒤로
      </button>

      <div style={styles.card}>

        {/* 예약 확인 완료 표시 */}
        <div style={styles.checkIcon}>✅</div>
        <h2 style={styles.title}>예약이 확인되었습니다</h2>

        {/* 예약 상세 정보 */}
        <div style={styles.infoBox}>
          <InfoRow label="성함"   value={reservation.name} />
          <InfoRow label="시간"   value={`${reservation.time_slot}:00 ~ ${reservation.time_slot + 1}:00`} />
          <InfoRow label="상담실" value={roomLabel} />
        </div>

        {/* 안내 멘트 미리보기 */}
        <p style={styles.ttsPreview}>
          "{reservation.name}님 {reservation.time_slot}시 상담 예약으로{' '}
          {roomLabel}로 안내합니다"
        </p>

        {error && <p style={styles.error}>{error}</p>}

        <button
          onClick={handleStart}
          disabled={loading}
          style={{ ...styles.startBtn, opacity: loading ? 0.6 : 1 }}
        >
          {loading ? '배정 중...' : '안내 시작'}
        </button>

      </div>
    </div>
  );
}

// 예약 정보 한 줄 표시 컴포넌트
function InfoRow({ label, value }) {
  return (
    <div style={infoRowStyle.row}>
      <span style={infoRowStyle.label}>{label}</span>
      <span style={infoRowStyle.value}>{value}</span>
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
  checkIcon: {
    fontSize: 56,
  },
  title: {
    fontSize: 26,
    fontWeight: 700,
    color: '#1a202c',
    textAlign: 'center',
  },
  infoBox: {
    width: '100%',
    background: '#f8fafc',
    borderRadius: 12,
    padding: '20px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  // 로봇이 실제로 발화할 TTS 멘트를 방문자에게 미리 보여줌
  ttsPreview: {
    fontSize: 15,
    color: '#6b7280',
    textAlign: 'center',
    fontStyle: 'italic',
    lineHeight: 1.6,
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
    transition: 'opacity 0.2s',
  },
};

const infoRowStyle = {
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  label: {
    fontSize: 16,
    color: '#6b7280',
  },
  value: {
    fontSize: 20,
    fontWeight: 600,
    color: '#1a202c',
  },
};

export default CheckinResultPage;
