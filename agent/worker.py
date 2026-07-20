import subprocess
import time
import requests

SERVER_DEVICE_ID = "QKQ1.190910.002"
ADB_SERIAL = "100.72.18.121:5555"
SERVER_URL = "http://127.0.0.1:8000"
ADB_PATH = r"C:\Users\wikto\Desktop\platform-tools\adb.exe"

def run_adb(args):
    try:
        cmd = [ADB_PATH, "-s", ADB_SERIAL] + args
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return res.stdout.strip()
    except Exception as e:
        print(f"❌ [BŁĄD ADB]: {e}")
        return ""

def ensure_adb_connection():
    print(f"🔗 [STRAŻNIK] Sprawdzanie połączenia z {ADB_SERIAL}...")
    for _ in range(10):
        try:
            subprocess.run([ADB_PATH, "connect", ADB_SERIAL], capture_output=True, timeout=5)
            time.sleep(2)
            res = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True, timeout=5)
            if ADB_SERIAL in res.stdout and "offline" not in res.stdout:
                return True
        except:
            pass
        time.sleep(1)
    return False

def execute_command(cmd, payload=""):
    print(f"\n⚡ [AKCJA]: Wykonuję komendę: {cmd} | PAYLOAD: {payload}")

    if cmd == "CHANGE_IP":
        print(" -> [1/2] Wysyłam autonomiczny reset modemu SIM (Tailscale pozostaje aktywny)...")
        
        # KLUCZOWA ZMIANA:
        # 1. 'svc radio' resetuje TYLKO sieć komórkową (nie rusza Wi-Fi/Tailscale).
        # 2. Cały łańcuch (wyłącz -> czekaj 5s -> włącz) wysyłamy w jednej komendzie do wykonania 
        #    w tle (&) wewnątrz telefonu. Telefon sam wstanie, skrypt na PC na nic nie czeka w trakcie resetu!
        root_command = "sh -c 'svc radio power off; sleep 5; svc radio power on' >/dev/null 2>&1 &"
        run_adb(["shell", "su", "-c", f"{root_command}"])
        
        print(" -> [2/2] ⏳ Odliczam 15s na wynegocjowanie nowego IP od operatora LTE...")
        time.sleep(15)
        
        # Upewniamy się, że połączenie ADB jest stabilne po resecie
        ensure_adb_connection()
        return "SUCCESS_IP_CHANGED"

    elif cmd == "START_TAILSCALE":
        print(" -> Uruchamianie Tailscale...")
        run_adb(["shell", "monkey", "-p", "com.tailscale.ipn", "-c", "android.intent.category.LAUNCHER", "1"])
        return "SUCCESS_TAILSCALE"

    elif cmd == "START_PROXY":
        print(" -> Uruchamianie EveryProxy...")
        run_adb(["shell", "monkey", "-p", "com.everyproxy", "-c", "android.intent.category.LAUNCHER", "1"])
        return "SUCCESS_PROXY"

    elif cmd == "REBOOT":
        print(" -> Restartowanie urządzenia...")
        run_adb(["shell", "su", "-c", "reboot"])
        return "SUCCESS_REBOOT"

    elif cmd == "SHELL":
        print(f" -> Wykonywanie własnej komendy: {payload}")
        output = run_adb(["shell", payload])
        print(f" -> Wynik: {output}")
        return output if output else "SUCCESS_SHELL"

    return "IGNORED_UNKNOWN_COMMAND"

def main():
    print(f"🚀 AGENT STARTUJE DLA URZĄDZENIA: {SERVER_DEVICE_ID}")
    ensure_adb_connection()
    while True:
        try:
            res = requests.get(f"{SERVER_URL}/commands/next/{SERVER_DEVICE_ID}", timeout=3)
            if res.status_code == 200:
                data = res.json()
                if data and data.get("id"):
                    cmd_id = data.get("id")
                    command = data.get("command")
                    payload = data.get("payload", "")
                    
                    result = execute_command(command, payload)
                    
                    requests.post(
                        f"{SERVER_URL}/commands/done", 
                        json={"command_id": cmd_id, "result": result}, 
                        timeout=3
                    )
        except Exception:
            pass
        time.sleep(1)

if __name__ == "__main__":
    main()