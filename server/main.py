from datetime import datetime
import json
import os
import sqlite3
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(BASE_DIR, "dashboard", "index.html")):
    INDEX_PATH = os.path.join(BASE_DIR, "dashboard", "index.html")
else:
    INDEX_PATH = os.path.join(BASE_DIR, "index.html")

IP_FILE = os.path.join(BASE_DIR, "used_ips.json")
IP_HISTORY_FILE = os.path.join(BASE_DIR, "ip_change_history.json")
DB_FILE = os.path.join(BASE_DIR, "devices.db")

COMMANDS = []
DEVICES_STATE = {}


# ==========================================
# SEKCJA OBSŁUGI BAZY DANYCH SQLITE
# ==========================================

def init_db():
    """Inicjalizuje bazę danych z tabelą urządzeń i współrzędnych tap tap."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            custom_name TEXT DEFAULT 'Nowy Telefon',
            group_name TEXT DEFAULT 'Domyślna',
            every_proxy_x INTEGER DEFAULT 500,
            every_proxy_y INTEGER DEFAULT 1000,
            tailscale_x INTEGER DEFAULT 500,
            tailscale_y INTEGER DEFAULT 1000,
            is_active BOOLEAN DEFAULT 1,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def db_register_device(device_id: str, default_name: str = "Nowy Telefon", group_name: str = "Domyślna"):
    """Rejestruje urządzenie w bazie, jeśli jeszcze nie występuje."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT device_id FROM devices WHERE device_id = ?", (device_id,))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO devices (device_id, custom_name, group_name) VALUES (?, ?, ?)
        ''', (device_id, default_name, group_name))
        conn.commit()
    conn.close()


def db_get_device(device_id: str):
    """Pobiera pełny rekord urządzenia (nazwa, grupa, współrzędne)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT custom_name, group_name, every_proxy_x, every_proxy_y, tailscale_x, tailscale_y
        FROM devices WHERE device_id = ?
    ''', (device_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "custom_name": row[0],
        "group_name": row[1],
        "every_proxy_x": row[2],
        "every_proxy_y": row[3],
        "tailscale_x": row[4],
        "tailscale_y": row[5],
    }


def db_get_coords(device_id: str):
    """Pobiera z bazy współrzędne tap tap dla podanego urządzenia."""
    device = db_get_device(device_id)
    if device:
        return {
            "every_proxy_x": device["every_proxy_x"],
            "every_proxy_y": device["every_proxy_y"],
            "tailscale_x": device["tailscale_x"],
            "tailscale_y": device["tailscale_y"],
        }
    return {
        "every_proxy_x": 500,
        "every_proxy_y": 1000,
        "tailscale_x": 500,
        "tailscale_y": 1000,
    }


def db_update_meta(device_id: str, custom_name: str = None, group_name: str = None):
    """Aktualizuje nazwę i/lub grupę urządzenia."""
    db_register_device(device_id)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if custom_name is not None:
        cursor.execute(
            "UPDATE devices SET custom_name = ? WHERE device_id = ?",
            (custom_name.strip() or "Nowy Telefon", device_id),
        )
    if group_name is not None:
        cursor.execute(
            "UPDATE devices SET group_name = ? WHERE device_id = ?",
            (group_name.strip() or "Domyślna", device_id),
        )
    conn.commit()
    conn.close()


def db_update_coords(device_id: str, every_proxy_x: int, every_proxy_y: int, tailscale_x: int, tailscale_y: int):
    """Zapisuje współrzędne tap tap dla urządzenia."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO devices (device_id, every_proxy_x, every_proxy_y, tailscale_x, tailscale_y)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
            every_proxy_x = excluded.every_proxy_x,
            every_proxy_y = excluded.every_proxy_y,
            tailscale_x = excluded.tailscale_x,
            tailscale_y = excluded.tailscale_y
    ''', (device_id, every_proxy_x, every_proxy_y, tailscale_x, tailscale_y))
    conn.commit()
    conn.close()


def ensure_runtime_state(device_id: str, default_name: str = None):
    """Dopina urządzenie do pamięci runtime i synchronizuje nazwę z DB."""
    db_register_device(device_id, default_name=default_name or f"Telefon_{device_id[:6]}")
    meta = db_get_device(device_id) or {}
    name = meta.get("custom_name") or default_name or f"Telefon_{device_id[:6]}"
    group = meta.get("group_name") or "Domyślna"

    if device_id not in DEVICES_STATE:
        DEVICES_STATE[device_id] = {
            "name": name,
            "group": group,
            "last_seen": 0,
            "tailscale": False,
            "every_proxy": False,
            "battery": 0,
            "battery_temp": 0.0,
            "ip": "0.0.0.0",
            "tailscale_ip": "",
            "every_proxy_address": "",
        }
    else:
        DEVICES_STATE[device_id]["name"] = name
        DEVICES_STATE[device_id]["group"] = group

    return DEVICES_STATE[device_id]


# Tworzymy strukturę tabeli przy starcie serwera
init_db()

# ==========================================
# POMOCNICZE FUNKCJE WEJŚCIA/WYJŚCIA (JSON)
# ==========================================

def load_ip_db():
    if not os.path.exists(IP_FILE):
        return {}
    try:
        with open(IP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_ip_db(data):
    with open(IP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def load_ip_history():
    if not os.path.exists(IP_HISTORY_FILE):
        return []
    try:
        with open(IP_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_ip_history(history):
    with open(IP_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)


# ==========================================
# ENDPOINTY SERWERA FASTAPI
# ==========================================

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return HTMLResponse(f"❌ Błąd: Brak pliku {INDEX_PATH}", status_code=404)


@app.get("/phones/")
def get_phones():
    now = time.time()
    phones_list = []
    for dev_id, state in DEVICES_STATE.items():
        ensure_runtime_state(dev_id)
        meta = db_get_device(dev_id) or {}
        is_online = (now - state["last_seen"]) < 40
        phones_list.append(
            {
                "device_id": dev_id,
                "name": meta.get("custom_name") or state.get("name") or f"Telefon_{dev_id[:6]}",
                "group": meta.get("group_name") or state.get("group") or "Domyślna",
                "online": is_online,
                "tailscale": state.get("tailscale", False),
                "every_proxy": state.get("every_proxy", False),
                "battery": state.get("battery", 0),
                "battery_temp": state.get("battery_temp", 0),
                "ip": state.get("ip", "0.0.0.0"),
                "tailscale_ip": state.get("tailscale_ip", ""),
                "every_proxy_address": state.get("every_proxy_address", ""),
                "every_proxy_x": meta.get("every_proxy_x", 500),
                "every_proxy_y": meta.get("every_proxy_y", 1000),
                "tailscale_x": meta.get("tailscale_x", 500),
                "tailscale_y": meta.get("tailscale_y", 1000),
            }
        )

    phones_list.sort(key=lambda p: (p["group"].lower(), p["name"].lower()))
    return phones_list


@app.get("/phones/{device_id}/history")
def get_history(device_id: str):
    history = load_ip_history()
    return {
        "ip_history": history,
        "proxy": [{"old_ip": "-", "new_ip": DEVICES_STATE.get(device_id, {}).get("ip", "-")}],
        "tailscale": [],
    }


@app.get("/devices/{device_id}")
def get_device_details(device_id: str):
    ensure_runtime_state(device_id)
    meta = db_get_device(device_id)
    state = DEVICES_STATE.get(device_id, {})
    return {
        "device_id": device_id,
        "name": meta["custom_name"] if meta else state.get("name"),
        "group": meta["group_name"] if meta else state.get("group", "Domyślna"),
        "every_proxy_x": meta["every_proxy_x"] if meta else 500,
        "every_proxy_y": meta["every_proxy_y"] if meta else 1000,
        "tailscale_x": meta["tailscale_x"] if meta else 500,
        "tailscale_y": meta["tailscale_y"] if meta else 1000,
        "online": (time.time() - state.get("last_seen", 0)) < 40 if state else False,
    }


@app.post("/devices/{device_id}/meta")
async def set_device_meta(device_id: str, request: Request):
    """Ustawia nazwę i grupę telefonu z dashboardu."""
    data = await request.json()
    custom_name = data.get("custom_name")
    group_name = data.get("group_name")

    db_update_meta(device_id, custom_name=custom_name, group_name=group_name)
    state = ensure_runtime_state(device_id)
    if custom_name is not None:
        state["name"] = custom_name.strip() or state["name"]
    if group_name is not None:
        state["group"] = group_name.strip() or "Domyślna"

    return {
        "status": "ok",
        "device_id": device_id,
        "name": state["name"],
        "group": state["group"],
    }


@app.post("/devices/{device_id}/coords")
async def set_device_coords(device_id: str, request: Request):
    """API pozwalające ustawić z poziomu dashboardu unikalne współrzędne tap tap dla telefonu."""
    data = await request.json()
    px_x = int(data.get("every_proxy_x", 500))
    px_y = int(data.get("every_proxy_y", 1000))
    ts_x = int(data.get("tailscale_x", 500))
    ts_y = int(data.get("tailscale_y", 1000))

    db_register_device(device_id)
    db_update_coords(device_id, px_x, px_y, ts_x, ts_y)
    ensure_runtime_state(device_id)

    return {
        "status": "ok",
        "message": f"Zapisano nowe współrzędne dla {device_id}",
        "every_proxy_x": px_x,
        "every_proxy_y": px_y,
        "tailscale_x": ts_x,
        "tailscale_y": ts_y,
    }


@app.post("/devices/{device_id}/settings")
async def set_device_settings(device_id: str, request: Request):
    """Jednym requestem zapisuje nazwę, grupę i współrzędne."""
    data = await request.json()

    custom_name = data.get("custom_name")
    group_name = data.get("group_name")
    px_x = int(data.get("every_proxy_x", 500))
    px_y = int(data.get("every_proxy_y", 1000))
    ts_x = int(data.get("tailscale_x", 500))
    ts_y = int(data.get("tailscale_y", 1000))

    db_register_device(device_id)
    db_update_meta(device_id, custom_name=custom_name, group_name=group_name)
    db_update_coords(device_id, px_x, px_y, ts_x, ts_y)

    state = ensure_runtime_state(device_id)
    if custom_name is not None:
        state["name"] = custom_name.strip() or state["name"]
    if group_name is not None:
        state["group"] = group_name.strip() or "Domyślna"

    return {
        "status": "ok",
        "device_id": device_id,
        "name": state["name"],
        "group": state["group"],
        "every_proxy_x": px_x,
        "every_proxy_y": px_y,
        "tailscale_x": ts_x,
        "tailscale_y": ts_y,
    }


@app.post("/commands/add")
async def add_command(request: Request):
    data = await request.json()
    data["id"] = int(time.time() * 1000)

    dev_id = data.get("device_id")
    if not dev_id:
        return {"status": "error", "message": "Brak device_id"}

    cmd = data.get("command")
    ensure_runtime_state(dev_id)

    # Dołączamy spersonalizowane współrzędne tap tap na podstawie bazy danych
    coords = db_get_coords(dev_id)
    if cmd == "START_PROXY":
        data["tap_x"] = coords["every_proxy_x"]
        data["tap_y"] = coords["every_proxy_y"]
    elif cmd == "START_TAILSCALE":
        data["tap_x"] = coords["tailscale_x"]
        data["tap_y"] = coords["tailscale_y"]

    if dev_id in DEVICES_STATE:
        DEVICES_STATE[dev_id]["last_seen"] = time.time()

    COMMANDS.append(data)
    print(f"\n>>> [SERWER] Dodano komendę z ID {data['id']}: {cmd} (Urządzenie: {dev_id}) tap=({data.get('tap_x')},{data.get('tap_y')})")
    return {"status": "ok", "tap_x": data.get("tap_x"), "tap_y": data.get("tap_y")}


@app.get("/commands/next/{device_id}")
def get_next_command(device_id: str):
    ensure_runtime_state(device_id)
    DEVICES_STATE[device_id]["last_seen"] = time.time()

    # Ważne: każdy telefon dostaje tylko swoje komendy
    for i, cmd in enumerate(COMMANDS):
        if cmd.get("device_id") == device_id:
            selected = COMMANDS.pop(i)
            print(f">>> [SERWER] Wysyłam komendę do telefonu ({device_id}): {selected.get('command')} tap=({selected.get('tap_x')},{selected.get('tap_y')})")
            return selected

    return {
        "id": 0,
        "device_id": device_id,
        "command": "",
        "payload": "",
        "executed": False,
        "tap_x": None,
        "tap_y": None,
    }


@app.post("/commands/done")
async def command_done(request: Request):
    data = await request.json()
    command_id = data.get("command_id")
    status = data.get("result") or data.get("status")
    message = data.get("message") or data.get("result")
    device_id = data.get("device_id")

    print(f">>> [SERWER] Wykonano komendę ID: {command_id}, wynik: {status}, IP: {message}")

    if status == "SUCCESS" and message:
        new_ip = str(message).strip()
        if "." in new_ip and len(new_ip.split(".")) == 4:
            ip_db = load_ip_db()
            now = time.time()
            seven_days = 7 * 24 * 60 * 60

            ip_db = {ip: ts for ip, ts in ip_db.items() if (now - ts) < seven_days}

            if new_ip in ip_db:
                print(f"⚠️ [IP MANAGER] Adres {new_ip} był używany w ciągu ostatnich 7 dni! Ponawiam zmianę...")
                if device_id:
                    retry_cmd = {
                        "id": int(time.time() * 1000),
                        "device_id": device_id,
                        "command": "CHANGE_IP",
                        "payload": "",
                        "executed": False,
                    }
                    COMMANDS.append(retry_cmd)
            else:
                print(f"✅ [IP MANAGER] Nowe unikalne IP: {new_ip}. Zapisuję do historii.")
                ip_db[new_ip] = now
                save_ip_db(ip_db)

                history = load_ip_history()
                formatted_date = datetime.now().strftime("%d.%m.%Y %H:%M")
                history.insert(0, {"date": formatted_date, "ip": new_ip, "device_id": device_id})
                save_ip_history(history[:50])

                if device_id and device_id in DEVICES_STATE:
                    DEVICES_STATE[device_id]["ip"] = new_ip

    return {"status": "ok"}


@app.get("/ip/check")
def check_ip(ip: str):
    ip_db = load_ip_db()
    now = time.time()
    if ip in ip_db and (now - ip_db[ip]) < 604800:
        return {"is_clean": False}
    ip_db[ip] = now
    save_ip_db(ip_db)
    return {"is_clean": True}


@app.post("/{path:path}")
@app.put("/{path:path}")
async def catch_all_phone_app(path: str, request: Request):
    try:
        try:
            data = await request.json()
        except Exception:
            data = dict(await request.form())

        dev_id = data.get("device_id")
        if not dev_id:
            return {"status": "error", "message": "Brak device_id"}

        # Rejestrujemy telefon w bazie danych SQLite
        default_name = data.get("name") or f"Telefon_{str(dev_id)[:6]}"
        ensure_runtime_state(dev_id, default_name=default_name)
        DEVICES_STATE[dev_id]["last_seen"] = time.time()

        for key in [
            "battery",
            "battery_temp",
            "ip",
            "tailscale",
            "tailscale_ip",
            "every_proxy",
            "every_proxy_address",
            "online",
        ]:
            if key in data:
                DEVICES_STATE[dev_id][key] = data[key]

        return {"status": "ok", "success": True}
    except Exception:
        return {"status": "ok"}
