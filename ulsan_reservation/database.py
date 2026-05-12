# FastAPI와 MySQL을 연결하는 SQLAlchemy 설정 파일
# 모든 DB 작업(쿼리, 트랜잭션)은 여기서 생성한 세션을 통해 이루어진다

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

# .env 파일에서 환경변수(DATABASE_URL 등)를 로드
load_dotenv()

# engine: MySQL에 실제로 접속하는 연결 객체
# .env의 DATABASE_URL을 읽어 MySQL에 연결한다
# 형식: mysql+pymysql://유저:비밀번호@호스트:포트/DB명
engine = create_engine(os.getenv("DATABASE_URL"))

# SessionLocal: DB 작업 단위(세션)를 생성하는 팩토리
# autocommit=False: 명시적으로 commit()을 호출해야 DB에 반영됨 (트랜잭션 안전)
# autoflush=False: commit 전에 자동으로 flush하지 않음
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base: SQLAlchemy 모델 클래스들이 상속할 베이스 클래스
# models.py에서 Base를 상속받아 테이블을 정의한다
Base = declarative_base()


def get_db():
    """
    FastAPI 의존성 주입(Dependency Injection)용 DB 세션 생성 함수

    요청이 들어올 때마다 새 세션을 열고, 요청이 끝나면 자동으로 닫는다
    routers/reservations.py의 엔드포인트 함수에서 Depends(get_db)로 사용

    yield를 사용하는 이유:
    - yield 이전: 세션 생성 (요청 시작)
    - yield: 세션을 엔드포인트 함수에 전달
    - finally: 예외 발생 여부와 관계없이 세션 종료 보장
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
