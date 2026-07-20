from pydantic import BaseModel


class CommandCreate(BaseModel):
    device_id: str
    command: str
    payload: str = ""


class CommandResult(BaseModel):
    command_id: int
    status: str
    result: str = ""