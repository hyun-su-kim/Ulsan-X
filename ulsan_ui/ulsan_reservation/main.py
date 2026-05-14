# FastAPI 애플리케이션 진입점
#
# 앱 생성, 테이블 자동 생성, 라우터 등록, APScheduler(노쇼 감지) 설정을 담당한다.

from contextlib import asynccontextmanager
from datetime import date, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine, SessionLocal
from routers import reservations
from routers import walkin, assign, robots, logs
import crud
import models


def _check_noshow():
    """
    노쇼(No-show) 감지 — APScheduler가 매시 10분에 1회 실행.

    오늘 날짜 + 현재 시각(hour)에 PENDING 상태인 예약을 찾아 로그를 생성한다.
    예약 상태는 변경하지 않는다 — 매니저가 연락 후 직접 처리.

    실행 시점 예시: 14:10 실행 → 오늘 14시 PENDING 예약을 노쇼로 기록
    """
    db = SessionLocal()
    try:
        today = date.today()
        current_hour = datetime.now().hour

        pending = (
            db.query(models.Reservation)
            .filter(
                models.Reservation.date == today,
                models.Reservation.time_slot == current_hour,
                models.Reservation.status == models.ReservationStatus.PENDING,
                # walk-in 행(name="현장방문")은 노쇼 체크 제외
                models.Reservation.name != "현장방문",
            )
            .all()
        )

        for r in pending:
            message = (
                f"{r.name}({r.phone[-4:]}) "
                f"{current_hour}시 예약 미방문"
            )
            crud.create_log(db, log_type="noshow", message=message)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 테이블 자동 생성 + APScheduler 시작
    Base.metadata.create_all(bind=engine)

    scheduler = AsyncIOScheduler()
    # 매일 09~16시, 정각으로부터 10분 후 1회 실행
    scheduler.add_job(
        _check_noshow,
        trigger="cron",
        hour="9-17",
        minute=10,
    )
    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(
    title="Ulsan 학원 안내 로봇 예약 서버",
    description="상담 예약 생성/조회/상태 관리 + 로봇 임무 배정 API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 기존 예약 라우터
app.include_router(reservations.router)

# 신규 라우터
app.include_router(walkin.router)    # /walkin/*
app.include_router(assign.router)    # /assign/*
app.include_router(robots.router)    # /robots/*
app.include_router(logs.router)      # /logs
