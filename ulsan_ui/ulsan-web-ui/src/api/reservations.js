// FastAPI 서버와 통신하는 함수 모음
// 모든 HTTP 요청을 이 파일에서 관리하여 API URL 변경 시 한 곳만 수정하면 됨

import axios from "axios";

// 서버 주소: .env의 REACT_APP_API_URL > 브라우저 접속 hostname:8000 순으로 결정
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || `http://${window.location.hostname}:8000`,
});

/**
 * 예약 생성
 * @param {Object} data - { name, phone, date, time_slot }
 * @returns 생성된 예약 정보 (배정된 상담실 포함)
 */
export const createReservation = async (data) => {
  const response = await api.post("/reservations/", data);
  return response.data;
};

/**
 * 특정 날짜의 만석 시간대 목록 조회
 * @param {string} date - "YYYY-MM-DD" 형식
 * @returns {number[]} 만석 시간대 정수 배열 (예: [10, 14])
 */
export const getFullSlots = async (date) => {
  const response = await api.get("/reservations/slots", { params: { date } });
  return response.data.full_slots;
};

/**
 * 본인 예약 목록 조회 (취소/변경 가능한 PENDING 예약만)
 * @param {string} name - 예약자 이름
 * @param {string} phone - 전화번호 끝 4자리
 * @returns 예약 목록 배열
 */
export const getMyReservations = async (name, phone) => {
  const response = await api.get("/reservations/my", { params: { name, phone } });
  return response.data;
};

/**
 * 예약 날짜/시간 변경
 * @param {number} id - 예약 id
 * @param {Object} data - { date, time_slot }
 * @returns 변경된 예약 정보 (재배정된 상담실 포함)
 */
export const updateReservation = async (id, data) => {
  const response = await api.put(`/reservations/${id}`, data);
  return response.data;
};

/**
 * 예약 취소
 * @param {number} id - 예약 id
 */
export const cancelReservation = async (id) => {
  await api.delete(`/reservations/${id}`);
};
