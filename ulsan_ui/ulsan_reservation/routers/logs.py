# 관제 로그 라우터
#
# GET /logs — 관제 GUI 알림 로그 목록 조회 (최신순)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=list[schemas.LogResponse])
def get_logs(limit: int = 100, db: Session = Depends(get_db)):
    """
    관제 GUI 알림 로그 목록 반환 (최신순, 기본 100건).

    로그 유형:
    - noshow        : APScheduler 매시 10분 — 당시간대 PENDING 예약 미방문
    - mission_start : POST /assign, /walkin/assign, /assign/classroom — 임무 배정
    - mission_complete : PATCH /assign/{id}/complete — 임무 정상 완료
    - mission_fail  : PATCH /assign/{id}/fail — 임무 실패 후 홈 복귀
    """
    return crud.get_logs(db, limit=limit)
