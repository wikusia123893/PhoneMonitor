from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server.database.database import SessionLocal
from server.models.command import Command
from server.schemas.command import CommandCreate, CommandResult

router = APIRouter(prefix="/commands", tags=["Commands"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/add")
def add_command(command: CommandCreate, db: Session = Depends(get_db)):
    print(
        f"\n!!! OTRZYMANO KOMENDĘ: {command.command} dla {command.device_id} !!!\n"
    )

    new_cmd = Command(
        device_id=command.device_id,
        command=command.command,
        payload=command.payload,
        status="PENDING",
    )

    db.add(new_cmd)
    db.commit()
    db.refresh(new_cmd)

    return {
        "status": "OK",
        "id": new_cmd.id,
    }


@router.get("/next/{device_id}")
def get_next_command(device_id: str, db: Session = Depends(get_db)):
    cmd = (
        db.query(Command)
        .filter(
            Command.device_id == device_id,
            Command.status == "PENDING",
        )
        .order_by(Command.id.asc())
        .first()
    )

    if not cmd:
        return {"id": 0}

    cmd.status = "RUNNING"
    cmd.started_at = datetime.utcnow()
    db.commit()

    return {
        "id": cmd.id,
        "command": cmd.command,
        "payload": cmd.payload,
    }


@router.post("/done")
def command_done(result: CommandResult, db: Session = Depends(get_db)):
    cmd = db.query(Command).filter(Command.id == result.command_id).first()

    if cmd:
        cmd.status = result.status
        cmd.result = result.result
        cmd.finished_at = datetime.utcnow()

        db.commit()

    return {"status": "OK"}