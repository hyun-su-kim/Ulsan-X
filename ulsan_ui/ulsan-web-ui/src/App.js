// 앱 최상단 컴포넌트
// 모든 페이지 공통 헤더(좌측 상단 아이콘)와 라우터를 관리한다

import { BrowserRouter, Routes, Route } from "react-router-dom";
import ReservationPage from "./pages/ReservationPage";
import ConfirmPage from "./pages/ConfirmPage";
import MyReservationsPage from "./pages/MyReservationsPage";
import icon from "./icon.png";
import "./App.css";

// 모든 페이지에 공통으로 표시되는 헤더
function Header() {
  return (
    <div style={{
      position: "fixed",      // 스크롤해도 항상 상단 고정
      top: 0,
      left: 0,
      width: "100%",
      height: 56,
      background: "#fff",
      borderBottom: "1px solid #eee",
      display: "flex",
      alignItems: "center",
      padding: "0 20px",
      zIndex: 1000,           // 다른 요소 위에 표시
      boxSizing: "border-box",
    }}>
      <img src={icon} alt="학원 로고" style={{ height: 54 }} />
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      {/* 헤더는 라우터 밖에서 렌더링 → 페이지 전환과 무관하게 항상 표시 */}
      <Header />

      {/* 헤더 높이(56px)만큼 본문 상단 여백 확보 */}
      <div style={{ paddingTop: 56 }}>
        <Routes>
          <Route path="/" element={<ReservationPage />} />
          <Route path="/confirm" element={<ConfirmPage />} />
          <Route path="/my-reservations" element={<MyReservationsPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
