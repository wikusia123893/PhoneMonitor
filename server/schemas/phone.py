from pydantic import BaseModel
from typing import Optional

class PhoneCreate(BaseModel):
    device_id: str
    name: str
    model: str
    android: str
    ip: str
    battery: int
    battery_temp: float = 0.0  # Dodaj to pole!
    tailscale: bool
    tailscale_ip: str
    every_proxy: bool