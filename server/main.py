import json
import os
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

COMMANDS = []

DEVICES_STATE = {
    "QKQ1.190910.002": {
        "name": "Xiaomi (Główny)",
        "last_seen": 0,
        "tailscale": True,
        "every_proxy": True,
        "battery": 88,
        "battery_temp": 31.5,
        "ip": "100.72.18.121",
    }
}


@app.get("/", response_class=HTMLResponse)
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
        is_online = (now - state["last_seen"]) < 10
        phones_list.append(
            {
                "device_id": dev_id,
                "name": state["name"],
                "online": is_online,
                "tailscale": state["tailscale"],
                "every_proxy": state["every_proxy"],
                "battery": state["battery"],
                "battery_temp": state["battery_temp"],
                "ip": state["ip"],
            }
        )
    return phones_list


@app.get("/phones/{device_id}/history")
def get_history(device_id: str):
    return {
        "proxy": [{"old_ip": "185.22.1.5", "new_ip": "37.111.2.1"}],
        "tailscale": [{"old_ip": "100.64.0.1", "new_ip": "100.64.0.2"}],
    }


@app.post("/commands/add")
async def add_command(request: Request):
    data = await request.json()
    data["id"] = int(time.time() * 1000)

    dev_id = data.get("device_id", "QKQ1.190910.002")
    cmd = data.get("command")
    if dev_id in DEVICES_STATE:
        DEVICES_STATE[dev_id]["last_seen"] = time.time()
        if cmd == "START_PROXY":
            DEVICES_STATE[dev_id]["every_proxy"] = not DEVICES_STATE[dev_id][
                "every_proxy"
            ]
        elif cmd == "START_TAILSCALE":
            DEVICES_STATE[dev_id]["tailscale"] = not DEVICES_STATE[dev_id][
                "tailscale"
            ]

    COMMANDS.append(data)
    print(f"\n>>> [SERWER] Dodano komendę z ID {data['id']}: {cmd}")
    return {"status": "ok"}


@app.get("/commands/next/{device_id}")
def get_next_command(device_id: str):
    if device_id in DEVICES_STATE:
        DEVICES_STATE[device_id]["last_seen"] = time.time()

    if COMMANDS:
        cmd = COMMANDS.pop(0)
        print(f">>> [SERWER] Wysyłam komendę do workera: {cmd['command']}")
        return cmd
    return {"id": 0}


@app.post("/commands/done")
async def command_done(request: Request):
    data = await request.json()
    print(
        f">>> [SERWER] Wykonano komendę ID: {data.get('command_id')}, wynik: {data.get('result')}\n"
    )
    return {"status": "ok"}


@app.get("/ip/check")
def check_ip(ip: str):
    if not os.path.exists(IP_FILE):
        ips = {}
    else:
        with open(IP_FILE, "r") as f:
            ips = json.load(f)
    now = time.time()
    if ip in ips and (now - ips[ip]) < 604800:
        return {"is_clean": False}
    ips[ip] = now
    with open(IP_FILE, "w") as f:
        json.dump(ips, f)
    return {"is_clean": True}


# --- UNIWERSALNY ŁAPACZ DLA APKI Z TELEFONU ---
@app.post("/{path:path}")
@app.put("/{path:path}")
async def catch_all_phone_app(path: str, request: Request):
    try:
        try:
            data = await request.json()
        except Exception:
            data = dict(await request.form())

        print(
            f"\n🔥 [SUKCES! APKA Z TELEFONU STRZELIŁA W ADRES: /{path}] 🔥"
        )
        print(f"📦 DANE: {data}\n")

        dev_id = data.get("device_id", "QKQ1.190910.002")
        if dev_id not in DEVICES_STATE:
            dev_id = "QKQ1.190910.002"

        DEVICES_STATE[dev_id]["last_seen"] = time.time()
        for key in [
            "battery",
            "battery_temp",
            "ip",
            "tailscale",
            "every_proxy",
            "online",
        ]:
            if key in data:
                DEVICES_STATE[dev_id][key] = data[key]

        return {"status": "ok", "success": True}
    except Exception as e:
        return {"status": "ok"}