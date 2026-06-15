// 앱 최상단 컴포넌트 — 페이지 라우팅 관리
// React Router v6 기준: 각 경로에 대응하는 페이지 컴포넌트를 등록한다

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import './App.css';

import HomePage           from './pages/HomePage';
import CheckinPage        from './pages/CheckinPage';
import CheckinResultPage  from './pages/CheckinResultPage';
import WalkinPage         from './pages/WalkinPage';
import WalkinRoomPage     from './pages/WalkinRoomPage';
import ClassroomPage      from './pages/ClassroomPage';
import GuidingPage        from './pages/GuidingPage';
import WaitingPage        from './pages/WaitingPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 홈 — 예약 조회 / 현장 방문 선택 */}
        <Route path="/"                element={<HomePage />} />

        {/* 예약 조회 흐름 */}
        <Route path="/checkin"         element={<CheckinPage />} />
        <Route path="/checkin/result"  element={<CheckinResultPage />} />

        {/* 현장 방문 흐름 */}
        <Route path="/walkin"          element={<WalkinPage />} />
        <Route path="/walkin/room"     element={<WalkinRoomPage />} />
        <Route path="/walkin/classroom" element={<ClassroomPage />} />

        {/* 공통 — 로봇 안내 중 화면 */}
        <Route path="/guiding"         element={<GuidingPage />} />

        {/* 공통 — 로봇 만차 시 대기 안내 화면 (큐 진입) */}
        <Route path="/waiting"         element={<WaitingPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
