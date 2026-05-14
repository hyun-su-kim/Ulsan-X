// 예약 폼 페이지
// 방문자(학부모/학생)가 상담 예약을 입력하고 제출하는 화면
// 제출 성공 시 ConfirmPage로 이동하며 예약 정보를 함께 전달한다

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { createReservation, getFullSlots } from "../api/reservations";

// 예약 가능한 시간대 목록 (09시~17시, 정수로 표현)
const TIME_SLOTS = [9, 10, 11, 12, 13, 14, 15, 16, 17];

// 주말 선택 불가 필터 (react-datepicker filterDate prop에 사용)
const isWeekday = (date) => {
  const day = date.getDay(); // 0=일요일, 6=토요일
  return day !== 0 && day !== 6;
};

function ReservationPage() {
  const navigate = useNavigate();

  const [name, setName]               = useState("");
  const [phone, setPhone]             = useState("");
  const [selectedDate, setSelectedDate] = useState(null);
  const [timeSlot, setTimeSlot]       = useState("");
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState("");

  // 만석 시간대 목록: 날짜 선택 시 API 조회 후 저장
  const [fullSlots, setFullSlots]     = useState([]);

  // 예약 가능 날짜 범위: 오늘 ~ 2주 후
  const today        = new Date();
  const twoWeeksLater = new Date();
  twoWeeksLater.setDate(today.getDate() + 14);

  // 날짜 선택 핸들러: 날짜 변경 시 만석 시간대 조회 후 시간 선택 초기화
  const handleDateChange = async (date) => {
    setSelectedDate(date);
    setTimeSlot("");       // 날짜 바뀌면 시간 선택 초기화
    setFullSlots([]);

    if (!date) return;

    try {
      const full = await getFullSlots(formatDate(date));
      setFullSlots(full);
    } catch {
      // 조회 실패 시 무시 (만석 표시 없이 진행)
    }
  };

  // Date 객체 → "YYYY-MM-DD" 문자열 변환 (FastAPI 입력 형식)
  const formatDate = (date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!selectedDate) {
      setError("날짜를 선택해주세요.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const result = await createReservation({
        name,
        phone,
        date: formatDate(selectedDate),
        time_slot: parseInt(timeSlot),
      });
      // 예약 성공 → 확인 페이지로 이동하며 예약 정보 전달
      navigate("/confirm", { state: { reservation: result } });
    } catch (err) {
      setError(err.response?.data?.detail || "예약 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 480, margin: "60px auto", padding: "0 20px" }}>
      <h2>상담 예약</h2>
      <p style={{ color: "#666" }}>평일 09:00 ~ 17:00 / 1시간 단위</p>

      <form onSubmit={handleSubmit}>

        <div style={{ marginBottom: 16 }}>
          <label>이름</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="홍길동"
            required
            style={{ display: "block", width: "100%", padding: 8, marginTop: 4 }}
          />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label>전화번호</label>
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="01012341234"
            required
            style={{ display: "block", width: "100%", padding: 8, marginTop: 4 }}
          />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label>날짜</label>
          <div style={{ marginTop: 4 }}>
            <DatePicker
              selected={selectedDate}
              onChange={handleDateChange}
              filterDate={isWeekday}
              minDate={today}
              maxDate={twoWeeksLater}
              dateFormat="yyyy-MM-dd"
              placeholderText="날짜 선택"
            />
          </div>
        </div>

        <div style={{ marginBottom: 24 }}>
          <label>시간</label>
          <select
            value={timeSlot}
            onChange={(e) => setTimeSlot(e.target.value)}
            required
            style={{ display: "block", width: "100%", padding: 8, marginTop: 4 }}
          >
            <option value="">시간 선택</option>
            {TIME_SLOTS.map((slot) => {
              const isFull = fullSlots.includes(slot);
              return (
                // 만석 시간대: disabled + "(마감)" 표시 → 브라우저가 자동으로 회색 처리
                <option key={slot} value={slot} disabled={isFull}>
                  {String(slot).padStart(2, "0")}:00 ~ {String(slot + 1).padStart(2, "0")}:00
                  {isFull ? " (마감)" : ""}
                </option>
              );
            })}
          </select>
        </div>

        {error && <p style={{ color: "red", marginBottom: 16 }}>{error}</p>}

        <button
          type="submit"
          disabled={loading}
          style={{ width: "100%", padding: 12, fontSize: 16 }}
        >
          {loading ? "예약 중..." : "예약하기"}
        </button>
      </form>

      {/* 내 예약 조회/취소/변경 페이지 이동 링크 */}
      <p style={{ textAlign: "center", marginTop: 24 }}>
        <button
          onClick={() => navigate("/my-reservations")}
          style={{ background: "none", border: "none", color: "#1976d2", cursor: "pointer", fontSize: 14 }}
        >
          내 예약 조회 / 취소 / 변경
        </button>
      </p>
    </div>
  );
}

export default ReservationPage;
