// FastAPI 서버와 통신하는 함수 모음
// 모든 HTTP 요청을 이 파일에서 관리한다 — URL 변경 시 여기만 수정하면 됨
//
// 서버 주소는 .env의 REACT_APP_API_URL에서 읽는다
// 태블릿과 관제 노트북이 같은 WiFi에 연결되어 있어야 한다

import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://192.168.0.115:8000',
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
 * 예약 체크인 후 IDLE 로봇에 임무 배정 요청
 * wego_dispatcher가 이 요청을 감지해 /goal_destination, /speak_text 토픽을 발행한다
 *
 * @param {number} reservationId - 예약 id
 * @returns { robot: "limo1" | "limo2" }
 * @throws 503: 사용 가능한 로봇 없음
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
 * @returns { reservation_id: 5, robot: "limo1" }
 * @throws 503: 사용 가능한 로봇 없음
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
 * @returns { robot: "limo1" }
 * @throws 503: 사용 가능한 로봇 없음
 */
export const assignClassroom = async (destination) => {
  const response = await api.post('/assign/classroom', { destination });
  return response.data;
};

// ── 로봇 상태 조회 ───────────────────────────────────────────────────────────

/**
 * 두 로봇의 현재 상태 조회
 * GuidingPage에서 0.5초마다 폴링해 로봇 귀환 여부를 감지한다
 * wego_dispatcher가 robot_status 토픽을 구독해 FastAPI에 상태를 업데이트한다
 *
 * @returns { limo1: "IDLE"|"BUSY"|"RETURNING"|"WAITING", limo2: ... }
 */
export const getRobotStatus = async () => {
  const response = await api.get('/robots/status');
  return response.data;
};
