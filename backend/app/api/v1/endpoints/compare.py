from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.video import AnalysisSession, Video
from app.services.procedure_comparison import compare_procedures

router = APIRouter()


def _latest_completed_analysis(db: Session, video_id: UUID) -> AnalysisSession | None:
    return (
        db.query(AnalysisSession)
        .filter(AnalysisSession.video_id == video_id, AnalysisSession.status == "completed")
        .order_by(AnalysisSession.created_at.desc())
        .first()
    )


@router.get("")
def get_procedure_comparison(
    video_a_id: UUID = Query(...),
    video_b_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    if video_a_id == video_b_id:
        raise HTTPException(status_code=400, detail="Choose two different procedures")

    videos = db.query(Video).filter(
        Video.id.in_([video_a_id, video_b_id]),
        Video.user_id == current_user.id,
    ).all()
    videos_by_id = {video.id: video for video in videos}
    if video_a_id not in videos_by_id:
        raise HTTPException(status_code=404, detail="Procedure A not found")
    if video_b_id not in videos_by_id:
        raise HTTPException(status_code=404, detail="Procedure B not found")

    analysis_a = _latest_completed_analysis(db, video_a_id)
    analysis_b = _latest_completed_analysis(db, video_b_id)
    if not analysis_a:
        raise HTTPException(status_code=409, detail="Procedure A does not have a completed analysis")
    if not analysis_b:
        raise HTTPException(status_code=409, detail="Procedure B does not have a completed analysis")

    return compare_procedures(
        db,
        videos_by_id[video_a_id],
        analysis_a,
        videos_by_id[video_b_id],
        analysis_b,
    )
