import os
import time
import httpx
import psycopg2
from datetime import datetime

ADB_HOST = os.getenv("ANDROID_EMULATOR_HOST", "android-emulator")
ADB_PORT = os.getenv("ANDROID_EMULATOR_PORT", "5555")
ADB = f"adb -H {ADB_HOST} -P {ADB_PORT}"

PG_CONN = None

def get_pg_conn():
    global PG_CONN
    if PG_CONN is None or PG_CONN.closed:
        PG_CONN = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "shared-postgres"),
            port=os.getenv("POSTGRES_PORT", "5433"),
            dbname=os.getenv("POSTGRES_DB", "btc_trading"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "shared_memory_2026")
        )
        PG_CONN.autocommit = True
    return PG_CONN

def run_ad_test():
    session_id = f"sess_{int(time.time())}"
    # Abrir o app
    os.system(f"{ADB} shell am start -n com.tap.gallery/.MainActivity")
    time.sleep(10)
    # Dump UI e procurar botão de ad (simplificado)
    os.system(f"{ADB} shell uiautomator dump /sdcard/ui.xml")
    os.system(f"{ADB} pull /sdcard/ui.xml ./ui.xml")
    with open("./ui.xml") as f:
        ui = f.read()
    if "Assistir" in ui or "Watch" in ui:
        # Simula tap no botão (coordenadas fixas, ajustar conforme necessário)
        os.system(f"{ADB} shell input tap 500 1600")
        time.sleep(30)  # Espera ad rodar
        # Verifica se reward foi creditado (simplificado)
        os.system(f"{ADB} shell uiautomator dump /sdcard/ui2.xml")
        os.system(f"{ADB} pull /sdcard/ui2.xml ./ui2.xml")
        with open("./ui2.xml") as f2:
            ui2 = f2.read()
        reward = "Recompensa" in ui2 or "Reward" in ui2
    else:
        reward = False
    # Loga resultado
    conn = get_pg_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ads.ad_test_results (session_id, ad_loaded, reward_granted, ad_network, response_type)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (session_id, True, reward, "unknown", "rewarded")
    )
    cur.close()
    print(f"[BOT] Teste concluído: reward={reward}")

def main():
    while True:
        run_ad_test()
        time.sleep(600)  # 10 min cooldown

if __name__ == "__main__":
    main()
