// 홈 화면 — 방문 유형 선택
//
// 태블릿 화면에 상시 표시되는 첫 번째 화면이다
// 방문자가 화면을 보고 예약 여부에 따라 버튼을 선택한다
//
// 흐름:
//   [예약 조회] → /checkin (이름 + 전화번호 입력)
//   [현장 방문] → /walkin  (방문 유형 선택)

import { useNavigate } from 'react-router-dom';
import icon from '../icon.png';

const PRIMARY = '#2563eb';

function HomePage() {
  const navigate = useNavigate();

  return (
    <div style={styles.container}>

      {/* 좌측 상단 로고 */}
      <img src={icon} alt="학원 로고" style={styles.logo} />

      {/* 안내 문구 + 버튼 영역 */}
      <p style={styles.subtitle}>방문 유형을 선택해주세요</p>

      {/* 선택 버튼 영역 — 터치 친화적 대형 버튼 2개 */}
      <div style={styles.buttonGroup}>

        {/* 사전 예약자 → 이름+전화번호 체크인 */}
        <button
          style={{ ...styles.card, borderTop: `6px solid ${PRIMARY}` }}
          onClick={() => navigate('/checkin')}
        >
          <span style={styles.cardIcon}>📋</span>
          <span style={styles.cardTitle}>예약 조회</span>
          <span style={styles.cardDesc}>사전에 예약하고 오신 분</span>
        </button>

        {/* 현장 방문자 또는 강의실 모르는 학생 */}
        <button
          style={{ ...styles.card, borderTop: `6px solid #059669` }}
          onClick={() => navigate('/walkin')}
        >
          <span style={styles.cardIcon}>🚶</span>
          <span style={styles.cardTitle}>현장 방문</span>
          <span style={styles.cardDesc}>예약 없이 오셨거나 강의실을 모르시는 분</span>
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
    gap: '48px',
    position: 'relative',
  },
  logo: {
    position: 'absolute',
    top: 24,
    left: 24,
    width: 180,
    objectFit: 'contain',
  },
  subtitle: {
    fontSize: 22,
    color: '#4b5563',
  },
  buttonGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: 24,
    width: '100%',
    maxWidth: 480,
  },
  card: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 10,
    padding: '36px 24px',
    background: '#ffffff',
    borderRadius: 16,
    boxShadow: '0 2px 12px rgba(0,0,0,0.08)',
    transition: 'transform 0.1s, box-shadow 0.1s',
  },
  cardIcon: {
    fontSize: 48,
  },
  cardTitle: {
    fontSize: 28,
    fontWeight: 700,
    color: '#1a202c',
  },
  cardDesc: {
    fontSize: 16,
    color: '#6b7280',
  },
};

export default HomePage;
