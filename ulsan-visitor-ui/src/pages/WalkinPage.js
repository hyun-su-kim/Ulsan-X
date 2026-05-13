// 현장 방문 유형 선택 페이지
//
// 예약 없이 방문했거나 강의실을 모르는 방문자를 위한 분기 화면
//
// [상담 예약 없이 방문]
//   → /walkin/room : 현재 시간대 빈 상담실 자동 조회 후 표시
//
// [강의실 안내]
//   → /walkin/classroom : 1~5강의실 버튼 선택 화면

import { useNavigate } from 'react-router-dom';

function WalkinPage() {
  const navigate = useNavigate();

  return (
    <div style={styles.container}>

      {/* 뒤로 가기 */}
      <button style={styles.backBtn} onClick={() => navigate('/')}>
        ← 뒤로
      </button>

      <h2 style={styles.title}>현장 방문</h2>
      <p style={styles.desc}>방문 목적을 선택해주세요</p>

      <div style={styles.buttonGroup}>

        {/* 상담 예약 없이 방문 — 빈 상담실 자동 배정 */}
        <button
          style={{ ...styles.card, borderLeft: '6px solid #2563eb' }}
          onClick={() => navigate('/walkin/room')}
        >
          <span style={styles.cardIcon}>💬</span>
          <div style={styles.cardText}>
            <span style={styles.cardTitle}>상담 예약 없이 방문</span>
            <span style={styles.cardDesc}>현재 비어있는 상담실로 안내해드립니다</span>
          </div>
        </button>

        {/* 강의실 안내 — 학생이 강의실 번호를 직접 선택 */}
        <button
          style={{ ...styles.card, borderLeft: '6px solid #059669' }}
          onClick={() => navigate('/walkin/classroom')}
        >
          <span style={styles.cardIcon}>🎓</span>
          <div style={styles.cardText}>
            <span style={styles.cardTitle}>강의실 안내</span>
            <span style={styles.cardDesc}>강의실 번호를 선택하면 로봇이 안내합니다</span>
          </div>
        </button>

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
    gap: 16,
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
  title: {
    fontSize: 32,
    fontWeight: 700,
    color: '#1a202c',
  },
  desc: {
    fontSize: 18,
    color: '#6b7280',
    marginBottom: 16,
  },
  buttonGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
    width: '100%',
    maxWidth: 480,
  },
  card: {
    display: 'flex',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 20,
    padding: '28px 24px',
    background: '#ffffff',
    borderRadius: 16,
    boxShadow: '0 2px 12px rgba(0,0,0,0.07)',
  },
  cardIcon: {
    fontSize: 40,
    flexShrink: 0,
  },
  cardText: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    textAlign: 'left',
  },
  cardTitle: {
    fontSize: 22,
    fontWeight: 700,
    color: '#1a202c',
  },
  cardDesc: {
    fontSize: 14,
    color: '#6b7280',
    lineHeight: 1.4,
  },
};

export default WalkinPage;
