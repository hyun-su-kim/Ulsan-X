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

    if data.date.weekday() >= 5:
        raise HTTPException(status_code=400, detail="평일만 예약 가능합니다.")

    if data.date < today:
        raise HTTPException(status_code=400, detail="오늘 이전 날짜는 예약할 수 없습니다.")

    if data.date > today + timedelta(weeks=2):
        raise HTTPException(status_code=400, detail="2주 이내만 예약 가능합니다.")

    result = crud.create_reservation(db, data)
    if not result:
        raise HTTPException(status_code=400, detail="해당 시간대는 예약이 모두 찼습니다.")

    return result


@router.get("/slots")
def get_full_slots(date: date, db: Session = Depends(get_db)):
    """
    특정 날짜의 만석 시간대 목록 조회 (웹 예약 UI용)

    날짜 선택 시 호출하여 만석 시간대를 프론트에서 비활성화할 때 사용
    쿼리 파라미터: date (YYYY-MM-DD)

    응답: { "full_slots": [10, 14] } 형태로 만석 시간대 정수 목록 반환
    """
    full_slots = crud.get_full_slots(db, date)
    return {"full_slots": full_slots}


@router.get("/today", response_model=list[schemas.ReservationResponse])
def get_today_reservations(db: Session = Depends(get_db)):
    """
    오늘 예약 전체 조회 (관제 GUI용)

    관제 GUI에서 오늘의 예약 목록과 각 예약의 진행 상태를 테이블로 표시할 때 사용
    """
    return crud.get_today_reservations(db, date.today())


@router.get("/my", response_model=list[schemas.ReservationResponse])
def get_my_reservations(name: str, phone: str, db: Session = Depends(get_db)):
    """
    본인 예약 목록 조회 (웹 예약 UI — 내 예약 조회/취소/변경)

    오늘 이후 PENDING 상태 예약만 반환한다 (취소/변경 가능한 예약만)
    쿼리 파라미터: name, phone (끝 4자리)

    응답:
    - 200: 예약 목록 (없으면 빈 리스트)
    """
    return crud.get_my_reservations(db, name, phone, date.today())


@router.get("/check", response_model=schemas.ReservationResponse)
def check_reservation(name: str, phone: str, db: Session = Depends(get_db)):
    """
    이름 + 전화번호 끝 4자리로 예약 조회 (터치 UI용)

    오늘 날짜의 PENDING 상태 예약만 조회하여 중복 체크인을 방지한다

    응답:
    - 200: 예약 정보 (배정된 상담실, 시간대 포함)
    - 404: 해당 조건의 예약 없음
    """
    result = crud.check_reservation(db, name, phone, date.today())
    if not result:
        raise HTTPException(status_code=404, detail="예약 정보를 찾을 수 없습니다.")
    return result


@router.put("/{reservation_id}", response_model=schemas.ReservationResponse)
def update_reservation(
    reservation_id: int,
    data: schemas.ReservationUpdate,
    db: Session = Depends(get_db),
):
    """
    예약 날짜/시간 변경 (웹 예약 UI)

    PENDING 상태 예약만 변경 가능하다
    변경 시 새 슬롯에 빈 상담실이 자동 재배정된다

    응답:
    - 200: 변경 성공 (재배정된 상담실 포함)
    - 400: 새 시간대 만석 / 주말 / 기간 초과
    - 404: 예약 없음 또는 변경 불가 상태
    """
    today = date.today()

    if data.date.weekday() >= 5:
        raise HTTPException(status_code=400, detail="평일만 예약 가능합니다.")

    if data.date < today:
        raise HTTPException(status_code=400, detail="오늘 이전 날짜로는 변경할 수 없습니다.")

    if data.date > today + timedelta(weeks=2):
        raise HTTPException(status_code=400, detail="2주 이내만 예약 가능합니다.")

    result, reason = crud.update_reservation(db, reservation_id, data)

    if reason == "not_found":
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없거나 변경 불가 상태입니다.")
    if reason == "full":
        raise HTTPException(status_code=400, detail="해당 시간대는 예약이 모두 찼습니다.")

    return result


@router.delete("/{reservation_id}", status_code=204)
def delete_reservation(reservation_id: int, db: Session = Depends(get_db)):
    """
    예약 취소 (웹 예약 UI)

    PENDING 상태 예약만 취소 가능하다
    IN_PROGRESS(안내 중), COMPLETED(완료) 예약은 취소 불가

    응답:
    - 204: 취소 성공 (응답 본문 없음)
    - 404: 예약 없음 또는 취소 불가 상태
    """
    success = crud.delete_reservation(db, reservation_id)
    if not success:
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없거나 취소 불가 상태입니다.")


@router.patch("/{reservation_id}", response_model=schemas.ReservationResponse)
def update_status(
    reservation_id: int,
    data: schemas.StatusUpdate,
    db: Session = Depends(get_db),
):
    """
    예약 상태 변경 (터치 UI / wego_behaviour FSM)

    터치 UI 체크인: PENDING → IN_PROGRESS
    FSM RETURNING 완료: IN_PROGRESS → COMPLETED

    응답:
    - 200: 상태 변경 성공
    - 404: 예약 없음
    """
    result = crud.update_status(db, reservation_id, data.status)
    if not result:
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없습니다.")
    return result
