from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from server.database.database import SessionLocal
from server.models.phone import Phone
from server.models.proxy_history import ProxyHistory
from server.models.tailscale_history import TailscaleHistory
from server.schemas.phone import PhoneCreate
from server.schemas.phone_update import PhoneUpdate

router = APIRouter(prefix="/phones", tags=["Phones"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.post("/register")
def register_phone(phone: PhoneCreate, db: Session = Depends(get_db)):
    db_phone = db.query(Phone).filter(Phone.device_id == phone.device_id).first()
    now = datetime.utcnow()
    if db_phone:
        if db_phone.ip != phone.ip:
            db.add(ProxyHistory(device_id=phone.device_id, old_ip=db_phone.ip, new_ip=phone.ip))
        if db_phone.tailscale_ip != phone.tailscale_ip:
            db.add(TailscaleHistory(device_id=phone.device_id, old_ip=db_phone.tailscale_ip, new_ip=phone.tailscale_ip))
        db_phone.name = phone.name
        db_phone.model = phone.model
        db_phone.android = phone.android
        db_phone.ip = phone.ip
        db_phone.battery = phone.battery
        db_phone.battery_temp = phone.battery_temp # Aktualizacja temp
        db_phone.tailscale = phone.tailscale
        db_phone.tailscale_ip = phone.tailscale_ip
        db_phone.every_proxy = phone.every_proxy
        db_phone.last_seen = now
        db.commit()
        db.refresh(db_phone)
        return {"status": "UPDATED", "id": db_phone.id, "message": "Telefon zaktualizowany"}

    new_phone = Phone(
        device_id=phone.device_id, name=phone.name, model=phone.model,
        android=phone.android, ip=phone.ip, battery=phone.battery,
        battery_temp=phone.battery_temp, # Dodanie temp
        tailscale=phone.tailscale, tailscale_ip=phone.tailscale_ip,
        every_proxy=phone.every_proxy, last_seen=now
    )
    db.add(new_phone)
    db.commit()
    db.refresh(new_phone)
    return {"status": "CREATED", "id": new_phone.id, "message": "Telefon dodany"}

@router.post("/heartbeat/{device_id}")
def heartbeat(device_id: str, db: Session = Depends(get_db)):
    phone = db.query(Phone).filter(Phone.device_id == device_id).first()
    if not phone: return {"status": "ERROR"}
    phone.last_seen = datetime.utcnow()
    db.commit()
    return {"status": "OK"}

@router.post("/update")
def update_phone(phone: PhoneUpdate, db: Session = Depends(get_db)):
    db_phone = db.query(Phone).filter(Phone.device_id == phone.device_id).first()
    if not db_phone:
        return {"status": "ERROR", "message": "Telefon nie istnieje"}

    if db_phone.ip != phone.ip:
        db.add(ProxyHistory(device_id=phone.device_id, old_ip=db_phone.ip, new_ip=phone.ip))
    if db_phone.tailscale_ip != phone.tailscale_ip:
        db.add(TailscaleHistory(device_id=phone.device_id, old_ip=db_phone.tailscale_ip, new_ip=phone.tailscale_ip))

    db_phone.battery = phone.battery
    db_phone.battery_temp = phone.battery_temp # <--- ZAPISANIE TEMPERATURY
    db_phone.ip = phone.ip
    db_phone.tailscale = phone.tailscale
    db_phone.tailscale_ip = phone.tailscale_ip
    db_phone.every_proxy = phone.every_proxy
    db_phone.last_seen = datetime.utcnow()

    db.commit()
    db.refresh(db_phone)
    return {"status": "OK", "message": "Status zaktualizowany"}

def phone_json(phone):
    diff = datetime.utcnow() - phone.last_seen
    seconds = int(diff.total_seconds())
    return {
        "id": phone.id,
        "device_id": phone.device_id,
        "name": phone.name,
        "model": phone.model,
        "android": phone.android,
        "battery": phone.battery,
        "battery_temp": phone.battery_temp, # <--- WYSŁANIE DO DASHBOARDU
        "tailscale": phone.tailscale,
        "tailscale_ip": phone.tailscale_ip,
        "every_proxy": phone.every_proxy,
        "ip": phone.ip,
        "last_seen": phone.last_seen,
        "last_seen_seconds": seconds,
        "online": seconds < 60
    }

@router.get("/")
def get_phones(db: Session = Depends(get_db)):
    phones = db.query(Phone).order_by(Phone.id.asc()).all()
    return [phone_json(phone) for phone in phones]

@router.get("/{device_id}")
def get_phone(device_id: str, db: Session = Depends(get_db)):
    phone = db.query(Phone).filter(Phone.device_id == device_id).first()
    if not phone: return {"status": "ERROR", "message": "Telefon nie istnieje"}
    return phone_json(phone)

@router.get("/{device_id}/history")
def get_phone_history(device_id: str, db: Session = Depends(get_db)):
    proxy_history = db.query(ProxyHistory).filter(ProxyHistory.device_id == device_id).order_by(ProxyHistory.id.desc()).all()
    tailscale_history = db.query(TailscaleHistory).filter(TailscaleHistory.device_id == device_id).order_by(TailscaleHistory.id.desc()).all()
    return {
        "proxy": [{"id": p.id, "old_ip": p.old_ip, "new_ip": p.new_ip} for p in proxy_history],
        "tailscale": [{"id": t.id, "old_ip": t.old_ip, "new_ip": t.new_ip} for t in tailscale_history]
    }