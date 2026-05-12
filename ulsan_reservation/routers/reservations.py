# 예약 관련 API 엔드포인트 정의
# URL 경로와 HTTP 메서드를 함수에 연결하고, 요청/응답을 처리한다
#
# 엔드포인트 함수의 동작 순서:
# 1. FastAPI가 요청 수신 → schemas로 입력 데이터 검증
# 2. Depends(get_db)로 DB 세션 자동 주입
# 3. crud 함수 호출 → DB 조회/수정
# 4. 결과를 schemas로 직렬화하여 JSON 응답 반환

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, timedelta
import crud
import schemas
from database import get_db

# prefix="/reservations": 이 라우터의 모든 경로 앞에 /reservations가 붙음
# tags=["reservations"]: Swagger 문서(/docs)에서 그룹 이름으로 표시됨
router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post("/", response_model=schemas.ReservationResponse, status_code=201)
def create_reservation(data: schemas.ReservationCreate, db: Session = Depends(get_db)):
    """
    예약 생성 (웹 예약 UI → 서버)

    사전 검증:
    - 평일(월~금)만 예약 가능
    - 예약 가능 기간: 당일 ~ 2주 이내
    - 상담실 배정: crud.create_reservation에서 자동 처리

    응답:
    - 201: 예약 성공 (배정된 상담실 포함)
    - 400: 해당 시간대 만석 / 주말 / 기간 초과
    """
    today = date.today()

    # 주말 예약 불가 (weekday: 0=월요일, 6=일요일)
    if data.date.weekday() >= 5:
        raise HTTPException(status_code=400, detail="평일만 예약 가능합니다.")

    # 당일 이전 날짜 예약 불가
    if data.date < today:
        raise HTTPException(status_code=400, detail="오늘 이전 날짜는 예약할 수 없습니다.")

    # 2주 초과 예약 불가
    if data.date > today + timedelta(weeks=2):
        raise HTTPException(status_code=400, detail="2주 이내만 예약 가능합니다.")

    result = crud.create_reservation(db, data)

    # crud에서 None 반환 = 해당 시간대 4개 상담실 모두 예약됨
    if not result:
        raise HTTPException(status_code=400, detail="해당 시간대는 예약이 모두 찼습니다.")

    return result


@router.get("/today", response_model=list[schemas.ReservationResponse])
def get_today_reservations(db: Session = Depends(get_db)):
    """
    오늘 예약 전체 조회 (관제 GUI용)

    관제 GUI에서 오늘의 예약 목록과 각 예약의 진행 상태(PENDING/IN_PROGRESS/COMPLETED)를
    테이블로 표시할 때 사용한다
    시간순(time_slot 오름차순)으로 정렬하여 반환

    응답:
    - 200: 오늘 예약 목록 (없으면 빈 리스트)
    """
    return crud.get_today_reservations(db, date.today())


@router.get("/check", response_model=schemas.ReservationResponse)
def check_reservation(name: str, phone: str, db: Session = Depends(get_db)):
    """
    이름 + 전화번호 끝 4자리로 예약 조회 (터치 UI용)

    터치 UI에서 방문자가 이름과 전화번호 끝 4자리를 입력했을 때 호출된다
    오늘 날짜의 PENDING 상태 예약만 조회하여 중복 체크인을 방지한다

    쿼리 파라미터:
    - name: 예약자 이름
    - phone: 전화번호 끝 4자리

    응답:
    - 200: 예약 정보 (배정된 상담실, 시간대 포함)
    - 404: 해당 조건의 예약 없음
    """
    result = crud.check_reservation(db, name, phone, date.today())

    if not result:
        raise HTTPException(status_code=404, detail="예약 정보를 찾을 수 없습니다.")

    return result


@router.patch("/{reservation_id}", response_model=schemas.ReservationResponse)
def update_status(
    reservation_id: int,
    data: schemas.StatusUpdate,
    db: Session = Depends(get_db),
):
    """
    예약 상태 변경

    호출 시점:
    - 터치 UI 안내 시작 버튼: PENDING → IN_PROGRESS (중복 체크인 방지)
    - wego_behaviour FSM RETURNING 완료: IN_PROGRESS → COMPLETED

    응답:
    - 200: 상태 변경 성공
    - 404: 해당 id 예약 없음
    """
    result = crud.update_status(db, reservation_id, data.status)

    if not result:
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없습니다.")

    return result
