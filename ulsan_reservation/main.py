# FastAPI 애플리케이션 진입점
# 앱 생성, 테이블 자동 생성, 라우터 등록을 담당한다

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# CORS 미들웨어 설정
# 브라우저는 다른 출처(포트/도메인)로 요청할 때 서버의 허용 여부를 먼저 확인한다
# React(3000포트) → FastAPI(8000포트) 요청이 이에 해당
# allow_origins=["*"]: 모든 출처 허용 (개발 중 편의상. 배포 시 실제 도메인으로 제한 권장)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],   # GET, POST, PATCH 등 모든 HTTP 메서드 허용
    allow_headers=["*"],   # 모든 헤더 허용
)

# 예약 관련 엔드포인트 등록
# routers/reservations.py에 정의된 모든 경로가 /reservations 접두사로 등록됨
app.include_router(reservations.router)
