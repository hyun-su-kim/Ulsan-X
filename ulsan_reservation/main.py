# FastAPI 애플리케이션 진입점
# 앱 생성, 테이블 자동 생성, 라우터 등록을 담당한다

from fastapi import FastAPI
from database import Base, engine
from routers import reservations

# 서버 시작 시 models.py에 정의된 클래스를 보고 MySQL에 테이블 자동 생성
# 테이블이 이미 존재하면 무시하고, 없을 때만 생성한다
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Ulsan 학원 안내 로봇 예약 서버",
    description="상담 예약 생성/조회/상태 관리 API",
    version="1.0.0",
    # 실행 후 http://localhost:8000/docs 에서 Swagger UI 자동 확인 가능
)

# 예약 관련 엔드포인트 등록
# routers/reservations.py에 정의된 모든 경로가 /reservations 접두사로 등록됨
app.include_router(reservations.router)
