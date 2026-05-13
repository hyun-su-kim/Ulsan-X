// 예약 조회 페이지 — 이름 + 전화번호 끝 4자리 입력
//
// 방문자가 사전 예약 시 입력한 이름과 전화번호 끝 4자리를 입력한다
// 태블릿 OS 키보드가 자동으로 올라오므로 커스텀 키패드는 구현하지 않는다
//
// 흐름:
//   입력 후 [확인] 클릭
//     → 성공: 예약 정보를 state로 넘겨 /checkin/result로 이동
//     → 실패(404): "예약 정보를 찾을 수 없습니다" 에러 표시

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkReservation } from '../api';

function CheckinPage() {
  const navigate = useNavigate();

  const [name, setName]           = useState('');
  const [phoneLast4, setPhone]    = useState('');
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // 전화번호 끝 4자리 숫자만 허용
    if (!/^\d{4}$/.test(phoneLast4)) {
      setError('전화번호 끝 4자리를 숫자로 입력해주세요.');
      return;
    }

    setLoading(true);
    try {
      const reservation = await checkReservation(name.trim(), phoneLast4);
      // 예약 정보를 다음 페이지로 전달 (React Router state 활용)
      navigate('/checkin/result', { state: { reservation } });
    } catch (err) {
      // 404: 오늘 날짜의 PENDING 예약이 없는 경우
      if (err.response?.status === 404) {
        setError('예약 정보를 찾을 수 없습니다. 이름과 전화번호를 확인해주세요.');
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
      <button style={styles.backBtn} onClick={() => navigate('/')}>
        ← 뒤로
      </button>

      <div style={styles.card}>
        <h2 style={styles.title}>예약 조회</h2>
        <p style={styles.desc}>예약 시 입력하신 정보를 입력해주세요</p>

        <form onSubmit={handleSubmit} style={styles.form}>

          {/* 이름 입력 — 한글 OS 키보드 활성화 */}
          <div style={styles.field}>
            <label style={styles.label}>이름</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="홍길동"
              required
              style={styles.input}
            />
          </div>

          {/* 전화번호 끝 4자리 — 숫자 키보드 활성화 */}
          <div style={styles.field}>
            <label style={styles.label}>전화번호 끝 4자리</label>
            <input
              type="tel"
              value={phoneLast4}
              onChange={(e) => setPhone(e.target.value.replace(/\D/g, '').slice(0, 4))}
              placeholder="1234"
              maxLength={4}
              required
              style={styles.input}
            />
          </div>

          {/* 에러 메시지 */}
          {error && <p style={styles.error}>{error}</p>}

          <button
            type="submit"
            disabled={loading || !name.trim() || phoneLast4.length !== 4}
            style={{
              ...styles.submitBtn,
              opacity: (loading || !name.trim() || phoneLast4.length !== 4) ? 0.5 : 1,
            }}
          >
            {loading ? '조회 중...' : '확인'}
          </button>

        </form>
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
  },
  title: {
    fontSize: 30,
    fontWeight: 700,
    color: '#1a202c',
    marginBottom: 8,
    textAlign: 'center',
  },
  desc: {
    fontSize: 16,
    color: '#6b7280',
    textAlign: 'center',
    marginBottom: 36,
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: 24,
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  label: {
    fontSize: 16,
    fontWeight: 600,
    color: '#374151',
  },
  input: {
    fontSize: 22,
    padding: '14px 16px',
    border: '2px solid #e5e7eb',
    borderRadius: 12,
    width: '100%',
    // 터치 시 포커스 강조
    transition: 'border-color 0.2s',
  },
  error: {
    fontSize: 15,
    color: '#ef4444',
    textAlign: 'center',
  },
  submitBtn: {
    marginTop: 8,
    padding: '18px',
    fontSize: 22,
    fontWeight: 700,
    background: '#2563eb',
    color: '#ffffff',
    borderRadius: 14,
    transition: 'opacity 0.2s',
  },
};

export default CheckinPage;
