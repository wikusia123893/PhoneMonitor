from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server.database.database import SessionLocal

from server.models.proxy_history import ProxyHistory
from server.models.tailscale_history import TailscaleHistory


router = APIRouter(
    prefix="/history",
    tags=["History"],
)


def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


@router.get("/proxy/{device_id}")
def proxy_history(
    device_id: str,
    db: Session = Depends(get_db)
):

    history = (

        db.query(ProxyHistory)

        .filter(
            ProxyHistory.device_id == device_id
        )

        .order_by(
            ProxyHistory.created_at.desc()
        )

        .all()

    )

    return [

        {

            "old_ip": item.old_ip,
            "new_ip": item.new_ip,
            "created_at": item.created_at

        }

        for item in history

    ]


@router.get("/tailscale/{device_id}")
def tailscale_history(
    device_id: str,
    db: Session = Depends(get_db)
):

    history = (

        db.query(TailscaleHistory)

        .filter(
            TailscaleHistory.device_id == device_id
        )

        .order_by(
            TailscaleHistory.created_at.desc()
        )

        .all()

    )

    return [

        {

            "old_ip": item.old_ip,
            "new_ip": item.new_ip,
            "created_at": item.created_at

        }

        for item in history

    ]