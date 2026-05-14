// 예약 완료 확인 페이지
// ReservationPage에서 예약 성공 후 navigate("/confirm", { state })로 이동
// 배정된 상담실, 날짜, 시간을 표시하여 방문자가 내용을 확인할 수 있게 한다

import { useLocation, useNavigate } from "react-router-dom";

// 상담실 이름을 사람이 읽기 쉬운 한국어로 변환
const ROOM_LABELS = {
  counseling_1:           "상담실 1",
  counseling_2:           "상담실 2",
  intensive_counseling_1: "집중 상담실 1",
  intensive_counseling_2: "집중 상담실 2",
};

function ConfirmPage() {
  const navigate = useNavigate();

  // useLocation으로 ReservationPage에서 전달한 state 수신
  // state.reservation: FastAPI 응답 예약 객체
  const { state } = useLocation();
  const reservation = state?.reservation;

  // 직접 URL 접근 등으로 state가 없는 경우 예약 페이지로 리다이렉트
  if (!reservation) {
    return (
      <div style={{ maxWidth: 480, margin: "60px auto", padding: "0 20px" }}>
        <p>예약 정보가 없습니다.</p>
        <button onClick={() => navigate("/")}>예약 페이지로 이동</button>
      </div>
    );
  }

  // time_slot 정수를 "14:00 ~ 15:00" 형식으로 변환
  const formatTimeSlot = (slot) =>
    `${String(slot).padStart(2, "0")}:00 ~ ${String(slot + 1).padStart(2, "0")}:00`;

  return (
    <div style={{ maxWidth: 480, margin: "60px auto", padding: "0 20px" }}>
      <h2>예약 완료</h2>

      <div style={{ background: "#f5f5f5", padding: 24, borderRadius: 8, marginTop: 24 }}>
        <p><strong>이름</strong>: {reservation.name}</p>
        <p><strong>날짜</strong>: {reservation.date}</p>
        <p><strong>시간</strong>: {formatTimeSlot(reservation.time_slot)}</p>
        <p>
          <strong>배정 상담실</strong>: {ROOM_LABELS[reservation.room] || reservation.room}
        </p>
      </div>

      <p style={{ color: "#666", marginTop: 16 }}>
        방문 당일 로봇 터치 화면에서 이름과 전화번호 끝 4자리를 입력해 주세요.
      </p>

      {/* 추가 예약 버튼 */}
      <button
        onClick={() => navigate("/")}
        style={{ marginTop: 24, width: "100%", padding: 12, fontSize: 16 }}
      >
        추가 예약하기
      </button>
    </div>
  );
}

export default ConfirmPage;
