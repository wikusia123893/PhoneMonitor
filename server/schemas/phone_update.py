from pydantic import BaseModel

class PhoneUpdate(BaseModel):
    device_id: str
    battery: int
    battery_temp: float
    ip: str
    tailscale: bool
    tailscale_ip: str
    tailscale_status: str
    every_proxy: bool
    every_proxy_type: str
    every_proxy_address: str
    online: bool