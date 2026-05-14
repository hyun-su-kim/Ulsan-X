// 내 예약 조회/취소/변경 페이지
// 이름 + 전화번호 끝 4자리를 입력하면 본인의 PENDING 예약 목록을 보여준다
// 각 예약에서 취소 또는 날짜/시간 변경이 가능하다

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { getMyReservations, cancelReservation, updateReservation } from "../api/reservations";

const TIME_SLOTS = [9, 10, 11, 12, 13, 14, 15, 16];

// 상담실 이름 한국어 변환
const ROOM_LABELS = {
  counseling_1:           "상담실 1",
  counseling_2:           "상담실 2",
  intensive_counseling_1: "집중 상담실 1",
  intensive_counseling_2: "집중 상담실 2",
};

// 주말 선택 불가 필터
const isWeekday = (date) => {
  const day = date.getDay();
  return day !== 0 && day !== 6;
};

// time_slot 정수 → "14:00 ~ 15:00" 형식 변환
const formatTimeSlot = (slot) =>
  `${String(slot).padStart(2, "0")}:00 ~ ${String(slot + 1).padStart(2, "0")}:00`;

// Date 객체 → "YYYY-MM-DD" 변환
const formatDate = (date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

function MyReservationsPage() {
  const navigate = useNavigate();

  // 본인 확인 입력 상태
  const [name, setName]   = useState("");
  const [phone, setPhone] = useState("");

  // 조회 결과 상태
  const [reservations, setReservations] = useState(null); // null: 조회 전, []: 결과 없음
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError]     = useState("");

  // 변경 모드 상태: 변경 중인 예약 id를 저장 (null이면 변경 모드 비활성)
  const [editingId, setEditingId]           = useState(null);
  const [editDate, setEditDate]             = useState(null);
  const [editTimeSlot, setEditTimeSlot]     = useState("");
  const [editLoading, setEditLoading]       = useState(false);
  const [editError, setEditError]           = useState("");

  const today        = new Date();
  const twoWeeksLater = new Date();
  twoWeeksLater.setDate(today.getDate() + 14);

  // 예약 목록 조회
  const handleSearch = async (e) => {
    e.preventDefault();
    setSearchLoading(true);
    setSearchError("");
    setReservations(null);
    setEditingId(null);

    try {
      const data = await getMyReservations(name, phone);
      setReservations(data);
    } catch (err) {
      setSearchError(err.response?.data?.detail || "조회 중 오류가 발생했습니다.");
    } finally {
      setSearchLoading(false);
    }
  };

  // 예약 취소
  const handleCancel = async (id) => {
    if (!window.confirm("예약을 취소하시겠습니까?")) return;

    try {
      await cancelReservation(id);
      // 취소 성공 후 목록에서 제거
      setReservations((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      alert(err.response?.data?.detail || "취소 중 오류가 발생했습니다.");
    }
  };

  // 변경 모드 진입: 선택한 예약의 현재 값으로 초기화
  const handleEditStart = (reservation) => {
    setEditingId(reservation.id);
    setEditDate(new Date(reservation.date)); // 문자열 → Date 객체 변환
    setEditTimeSlot(String(reservation.time_slot));
    setEditError("");
  };

  // 변경 취소 (변경 모드 종료)
  const handleEditCancel = () => {
    setEditingId(null);
    setEditError("");
  };

  // 예약 변경 제출
  const handleEditSubmit = async (id) => {
    if (!editDate) {
      setEditError("날짜를 선택해주세요.");
      return;
    }

    setEditLoading(true);
    setEditError("");

    try {
      const updated = await updateReservation(id, {
        date: formatDate(editDate),
        time_slot: parseInt(editTimeSlot),
      });

      // 변경 성공 후 목록에서 해당 예약만 업데이트
      setReservations((prev) =>
        prev.map((r) => (r.id === id ? updated : r))
      );
      setEditingId(null);
    } catch (err) {
      setEditError(err.response?.data?.detail || "변경 중 오류가 발생했습니다.");
    } finally {
      setEditLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 560, margin: "60px auto", padding: "0 20px" }}>
      <h2>내 예약 조회</h2>

      {/* 본인 확인 폼 */}
      <form onSubmit={handleSearch}>
        <div style={{ marginBottom: 12 }}>
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
          <label>전화번호 끝 4자리</label>
          <input
            type="text"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="1234"
            maxLength={4}
            required
            style={{ display: "block", width: "100%", padding: 8, marginTop: 4 }}
          />
        </div>

        {searchError && <p style={{ color: "red" }}>{searchError}</p>}

        <button type="submit" disabled={searchLoading} style={{ padding: "8px 24px" }}>
          {searchLoading ? "조회 중..." : "조회하기"}
        </button>
      </form>

      {/* 조회 결과 */}
      {reservations !== null && (
        <div style={{ marginTop: 32 }}>
          {reservations.length === 0 ? (
            <p style={{ color: "#666" }}>조회된 예약이 없습니다.</p>
          ) : (
            reservations.map((r) => (
              <div
                key={r.id}
                style={{
                  border: "1px solid #ddd",
                  borderRadius: 8,
                  padding: 16,
                  marginBottom: 16,
                }}
              >
                {/* 예약 기본 정보 */}
                <p><strong>날짜</strong>: {r.date}</p>
                <p><strong>시간</strong>: {formatTimeSlot(r.time_slot)}</p>
                <p><strong>상담실</strong>: {ROOM_LABELS[r.room] || r.room}</p>

                {/* 변경 모드: 해당 예약만 인라인 폼으로 전환 */}
                {editingId === r.id ? (
                  <div style={{ marginTop: 12, background: "#f9f9f9", padding: 12, borderRadius: 6 }}>
                    <p style={{ fontWeight: "bold", marginBottom: 8 }}>날짜/시간 변경</p>

                    <label>새 날짜</label>
                    <div style={{ marginTop: 4, marginBottom: 12 }}>
                      <DatePicker
                        selected={editDate}
                        onChange={(date) => setEditDate(date)}
                        filterDate={isWeekday}
                        minDate={today}
                        maxDate={twoWeeksLater}
                        dateFormat="yyyy-MM-dd"
                      />
                    </div>

                    <label>새 시간</label>
                    <select
                      value={editTimeSlot}
                      onChange={(e) => setEditTimeSlot(e.target.value)}
                      style={{ display: "block", width: "100%", padding: 8, marginTop: 4, marginBottom: 12 }}
                    >
                      {TIME_SLOTS.map((slot) => (
                        <option key={slot} value={slot}>
                          {String(slot).padStart(2, "0")}:00 ~ {String(slot + 1).padStart(2, "0")}:00
                        </option>
                      ))}
                    </select>

                    {editError && <p style={{ color: "red" }}>{editError}</p>}

                    <div style={{ display: "flex", gap: 8 }}>
                      <button
                        onClick={() => handleEditSubmit(r.id)}
                        disabled={editLoading}
                        style={{ padding: "6px 16px" }}
                      >
                        {editLoading ? "변경 중..." : "변경 확인"}
                      </button>
                      <button
                        onClick={handleEditCancel}
                        style={{ padding: "6px 16px", background: "#eee", border: "none" }}
                      >
                        취소
                      </button>
                    </div>
                  </div>
                ) : (
                  // 일반 모드: 취소/변경 버튼
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    <button
                      onClick={() => handleEditStart(r)}
                      style={{ padding: "6px 16px" }}
                    >
                      변경
                    </button>
                    <button
                      onClick={() => handleCancel(r.id)}
                      style={{ padding: "6px 16px", background: "#ff5252", color: "#fff", border: "none" }}
                    >
                      취소
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* 예약 페이지로 돌아가기 */}
      <button
        onClick={() => navigate("/")}
        style={{ marginTop: 16, background: "none", border: "none", color: "#1976d2", cursor: "pointer", fontSize: 14 }}
      >
        ← 예약 페이지로
      </button>
    </div>
  );
}

export default MyReservationsPage;
