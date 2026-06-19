// FastAPI 서버와 통신하는 함수 모음
// 모든 HTTP 요청을 이 파일에서 관리한다 — URL 변경 시 여기만 수정하면 됨
//
// 서버 주소: .env의 REACT_APP_API_URL > 브라우저 접속 hostname:8000 순으로 결정
// React 앱과 FastAPI가 같은 서버에서 실행되므로 IP가 바뀌어도 자동으로 맞춰진다

import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || `http://${window.location.hostname}:8000`,
});

// ── 예약 조회 흐름 ──────────────────────────────────────────────────────────

/**
 * 이름 + 전화번호 끝 4자리로 오늘 PENDING 예약 조회
 * 체크인 페이지에서 호출한다
 *
 * @param {string} name      - 예약자 이름
 * @param {string} phoneLast4 - 전화번호 끝 4자리
 * @returns 예약 정보 { id, name, time_slot, room, status }
 * @throws 404: 예약 없음 / 이미 체크인됨 / 안내 완료
 */
export const checkReservation = async (name, phoneLast4) => {
  const response = await api.get('/reservations/check', {
    params: { name, phone: phoneLast4 },
  });
  return response.data;
};

/**
 * 예약 체크인 후 임무 생성 요청
 * 로봇 선택은 ulsan_dispatcher가 디스패치 시점에 수행한다 — 배정 결과는
 * getMission(missionId) 폴링으로 확인
 *
 * @param {number} reservationId - 예약 id
 * @returns { mission_id: number, queued: boolean }  queued=true면 대기열 진입(로봇 만차)
 */
export const assignReservation = async (reservationId) => {
  const response = await api.post('/assign', { reservation_id: reservationId });
  return response.data;
};

// ── 현장 방문 — 상담 흐름 ───────────────────────────────────────────────────

/**
 * 현재 시간대에 배정 가능한 상담실 조회
 * 우선순위: counseling_1 → counseling_2 → intensive_counseling_1 → intensive_counseling_2
 * WalkinRoomPage 마운트 시 호출한다
 *
 * @returns { room: "counseling_2" }
 * @throws 404: 모든 상담실 배정됨
 */
export const getAvailableRoom = async () => {
  const response = await api.get('/walkin/rooms/available');
  return response.data;
};

/**
 * 현장 방문 상담실 배정 + 로봇 임무 할당
 * DB에 walk-in 예약 행을 삽입하고 IDLE 로봇에 임무를 배정한다
 * 관제 UI 알림 로그도 이 엔드포인트에서 생성된다
 *
 * @param {string} room - 배정할 상담실 키 (예: "counseling_2")
 * @returns { mission_id: number, room: string, queued: boolean }
 */
export const assignWalkin = async (room) => {
  const response = await api.post('/walkin/assign', { room });
  return response.data;
};

// ── 현장 방문 — 강의실 흐름 ─────────────────────────────────────────────────

/**
 * 강의실 안내 로봇 임무 할당 (DB 기록 없음)
 * 수업 강의실을 아는 학생이 로봇 안내만 요청하는 경우
 *
 * @param {string} destination - waypoints.yaml 키 (예: "classroom_1")
 * @returns { mission_id: number, queued: boolean }
 */
export const assignClassroom = async (destination) => {
  const response = await api.post('/assign/classroom', { classroom: destination });
  return response.data;
};

// ── 임무 상태 조회 ───────────────────────────────────────────────────────────

/**
 * 임무 상태 + 배정 로봇 조회
 * GuidingPage가 폴링해 배정(PENDING→ACTIVE)과 완료(COMPLETED)를 감지한다
 *
 * @param {number} missionId - 임무 id
 * @returns { status: "PENDING"|"ACTIVE"|"COMPLETED", robot_assigned: "limo1"|"limo2"|null }
 */
export const getMission = async (missionId) => {
  const response = await api.get(`/assign/${missionId}`);
  return response.data;
};
