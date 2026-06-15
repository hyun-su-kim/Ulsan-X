// 강의실 안내 페이지 — 1~5강의실 버튼 선택
//
// 수업 강의실 번호를 아는 학생이 버튼을 눌러 로봇 안내를 요청한다
// DB 기록 없이 바로 POST /assign/classroom 으로 로봇 임무를 배정한다
//
// 흐름:
//   버튼 선택 → POST /assign/classroom { destination: "classroom_N" }
//     → queued=false: /guiding으로 이동 (배정 폴링)
//     → queued=true : /waiting으로 이동 (대기 안내 후 홈 복귀)

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { assignClassroom } from '../api';

// waypoints.yaml에 정의된 classroom_1~5와 키 이름이 일치해야 한다
const CLASSROOMS = [
  { key: 'classroom_1', label: '1강의실' },
  { key: 'classroom_2', label: '2강의실' },
  { key: 'classroom_3', label: '3강의실' },
  { key: 'classroom_4', label: '4강의실' },
  { key: 'classroom_5', label: '5강의실' },
];

function ClassroomPage() {
  const navigate = useNavigate();

  const [loading, setLoading]   = useState(false);
  const [selected, setSelected] = useState(null); // 클릭 중인 버튼 키
  const [error, setError]       = useState('');

  const handleSelect = async (classroom) => {
    setError('');
    setSelected(classroom.key);
    setLoading(true);
    try {
      const result = await assignClassroom(classroom.key);
      if (result.queued) {
        navigate('/waiting', { state: { destination: classroom.label } });
      } else {
        navigate('/guiding', {
          state: {
            missionId:   result.mission_id,
            destination: classroom.label,
          },
        });
      }
    } catch (err) {
      setError('오류가 발생했습니다. 다시 시도해주세요.');
      setSelected(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>

      {/* 뒤로 가기 */}
      <button style={styles.backBtn} onClick={() => navigate('/walkin')} disabled={loading}>
        ← 뒤로
      </button>

      <h2 style={styles.title}>강의실 안내</h2>
      <p style={styles.desc}>수업 강의실 번호를 선택해주세요</p>

      {/* 강의실 버튼 그리드 — 2열 배치 */}
      <div style={styles.grid}>
        {CLASSROOMS.map((c) => (
          <button
            key={c.key}
            style={{
              ...styles.btn,
              opacity: (loading && selected !== c.key) ? 0.4 : 1,
              background: selected === c.key ? '#1d4ed8' : '#2563eb',
            }}
            onClick={() => handleSelect(c)}
            disabled={loading}
          >
            {loading && selected === c.key ? '배정 중...' : c.label}
          </button>
        ))}
      </div>

      {error && <p style={styles.error}>{error}</p>}

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
    gap: 20,
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
  },
  // 2열 그리드: 5개 버튼 → 2+2+1 배치
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 16,
    width: '100%',
    maxWidth: 480,
  },
  btn: {
    padding: '36px 16px',
    fontSize: 26,
    fontWeight: 700,
    color: '#ffffff',
    borderRadius: 16,
    boxShadow: '0 3px 10px rgba(37,99,235,0.3)',
    transition: 'opacity 0.2s, background 0.2s',
  },
  error: {
    fontSize: 15,
    color: '#ef4444',
    textAlign: 'center',
    maxWidth: 400,
  },
};

export default ClassroomPage;
