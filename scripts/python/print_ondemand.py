#!/usr/bin/env python3
"""
Print & Scan On-Demand Service — Gerencia VM Win10PrinterVM automaticamente.

Impressão:
- Inicia a VM apenas quando há pedido de impressão
- Aguarda WinRM ficar pronto
- Transfere arquivo via HTTP e imprime
- Desliga a VM após timeout de ociosidade (padrão: 5 min)

Scanner:
- WIA (padrão): usa scanner via Windows VM + WinRM (driver oficial Epson)
- SANE (fallback): libera USB, scanimage no host, reaproveita USB
- eSCL/AirScan: protocolo discoverable para simple-scan/GUI

Porta: 9877
Endpoints:
  POST /print        — envia arquivo para impressão (multipart ou path local)
  POST /scan         — digitaliza e retorna imagem (params: resolution, format, mode)
  GET  /scan/preview — scan rápido de preview (150dpi, jpeg)
  GET  /status       — status da VM e fila
  POST /vm/start     — força start da VM
  POST /vm/stop      — força stop da VM
  GET  /health       — healthcheck
  GET  /metrics      — métricas Prometheus
"""

import asyncio
import re
import logging
import os
import shutil
import subprocess
import tempfile
import time
import threading
from urllib.parse import quote as urlquote
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
import uvicorn
import base64
import uuid as uuid_mod
from xml.etree import ElementTree as ET

# ─── Configuração ───────────────────────────────────────────────
VM_NAME = os.getenv("PRINT_VM_NAME", "win10-printer")
VM_USER = os.getenv("PRINT_VM_USER", "homelab")
VM_PASS = os.getenv("PRINT_VM_PASS", "homelab")
VM_IP = os.getenv("PRINT_VM_IP", "192.168.122.10")
VM_MAC = os.getenv("PRINT_VM_MAC", "52:54:00:08:5a:8c")  # MAC KVM/libvirt
WINRM_PORT = int(os.getenv("PRINT_WINRM_PORT", "5985"))
PRINTER_NAME = os.getenv("PRINT_PRINTER_NAME", "EPSON L380 Series")
IDLE_TIMEOUT = int(os.getenv("PRINT_IDLE_TIMEOUT", "300"))  # 5 min
HTTP_PORT = int(os.getenv("PRINT_HTTP_PORT", "9876"))  # HTTP file server port
SERVICE_PORT = int(os.getenv("PRINT_SERVICE_PORT", "9877"))
USB_UUID = os.getenv("PRINT_USB_UUID", "4b036400-656c-4f21-a2de-26d4236054f7")
WINRM_TIMEOUT = int(os.getenv("PRINT_WINRM_TIMEOUT", "180"))  # max wait for WinRM
TEMP_DIR = "/tmp/print_ondemand"

# Scanner — SANE config
SCAN_METHOD = os.getenv("SCAN_METHOD", "wia")  # wia (Windows) ou sane (Linux)
SCAN_BACKEND = os.getenv("SCAN_BACKEND", "epson2")  # backend SANE (fallback)
SCAN_USB_VID = os.getenv("SCAN_USB_VID", "04b8")
SCAN_USB_PID = os.getenv("SCAN_USB_PID", "1120")
SCAN_DEFAULT_RESOLUTION = int(os.getenv("SCAN_DEFAULT_RESOLUTION", "300"))
SCAN_DEFAULT_FORMAT = os.getenv("SCAN_DEFAULT_FORMAT", "jpeg")
SCAN_DEFAULT_MODE = os.getenv("SCAN_DEFAULT_MODE", "Color")
SCAN_DIR = "/tmp/scans"

# eSCL (AirScan) protocol config
ESCL_UUID = os.getenv("ESCL_UUID", "e380-scan-homelab-0001")
ESCL_MAX_WIDTH = 2480   # A4 210mm in 1/300"
ESCL_MAX_HEIGHT = 3508  # A4 297mm in 1/300"
ESCL_MIN_WIDTH = 300
ESCL_MIN_HEIGHT = 300

# ─── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("print-ondemand")

# ─── Estado global ──────────────────────────────────────────────
state = {
    "vm_status": "unknown",      # stopped, starting, running, stopping
    "last_activity": None,       # timestamp da última impressão
    "idle_shutdown_at": None,    # quando vai desligar
    "jobs_completed": 0,
    "jobs_failed": 0,
    "jobs_total": 0,
    "current_job": None,
    "startup_time": None,
    "http_server_pid": None,
    # Scanner
    "scans_total": 0,
    "scans_completed": 0,
    "scans_failed": 0,
    "current_scan": None,
    "last_scan": None,
}

shutdown_timer: Optional[threading.Timer] = None
vm_lock = asyncio.Lock()
scan_lock = asyncio.Lock()  # evita scans simultâneos e conflitos com USB

# eSCL job tracking
escl_jobs: dict = {}
escl_job_counter = 0


# ─── Helpers VBoxManage ─────────────────────────────────────────
def run_virsh(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Executa virsh e retorna (returncode, stdout, stderr)."""
    cmd = ["sudo", "virsh"] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"


# Alias de compatibilidade
def run_vbox(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Alias legado — redireciona para run_virsh mapeando args VBox->virsh."""
    return run_virsh(args, timeout)


def get_vm_state() -> str:
    """Retorna estado atual da VM via virsh: running, poweroff, saved, etc."""
    rc, out, _ = run_virsh(["domstate", VM_NAME])
    if rc != 0:
        return "unknown"
    virsh_map = {
        "running": "running",
        "shut off": "poweroff",
        "paused": "paused",
        "in shutdown": "stopping",
        "pmsuspended": "saved",
        "saved": "saved",
        "crashed": "aborted",
        "dying": "stopping",
    }
    raw = out.strip().lower()
    return virsh_map.get(raw, raw)


def start_vm() -> bool:
    """Inicia a VM em modo headless."""
    current = get_vm_state()
    if current == "running":
        log.info("VM já está rodando")
        return True
    
    log.info(f"Iniciando VM {VM_NAME} (estado atual: {current})...")
    rc, out, err = run_virsh(["start", VM_NAME], timeout=60)
    if rc != 0:
        log.error(f"Falha ao iniciar VM: {err}")
        return False

    log.info("VM iniciada com sucesso")
    return True


def stop_vm(save_state: bool = False) -> bool:
    """Para a VM (acpipowerbutton ou savestate)."""
    current = get_vm_state()
    if current != "running":
        log.info(f"VM não está rodando (estado: {current})")
        return True
    
    if save_state:
        log.info("Salvando estado da VM (managedsave)...")
        rc, _, err = run_virsh(["managedsave", VM_NAME], timeout=120)
    else:
        log.info("Desligando VM via ACPI (virsh shutdown)...")
        rc, _, err = run_virsh(["shutdown", VM_NAME], timeout=30)
        # Aguardar desligamento gracioso (max 60s)
        for i in range(60):
            time.sleep(1)
            if get_vm_state() != "running":
                break
        # Se não desligou, forçar
        if get_vm_state() == "running":
            log.warning("VM não desligou via ACPI, forçando destroy...")
            rc, _, err = run_virsh(["destroy", VM_NAME], timeout=30)
    
    final = get_vm_state()
    log.info(f"VM estado final: {final}")
    return final != "running"


def find_usb_uuid() -> Optional[str]:
    """Encontra Epson L380 no host via lsusb (04b8:1120). Retorna 'bus-dev' ou None."""
    try:
        r = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=10)
        for line in r.stdout.splitlines():
            if "04b8:1120" in line.lower():
                # Linha: Bus 001 Device 003: ID 04b8:1120 ...
                parts = line.split()
                if len(parts) >= 4:
                    bus = parts[1].zfill(3)
                    dev = parts[3].rstrip(":").zfill(3)
                    return f"{bus}-{dev}"
    except Exception as e:
        log.warning(f"find_usb_uuid error: {e}")
    return None


# XML para passthrough USB Epson L380
_USB_HOSTDEV_XML = """<hostdev mode='subsystem' type='usb' managed='yes'>
  <source>
    <vendor id='0x04b8'/>
    <product id='0x1120'/>
  </source>
</hostdev>
"""


def _write_usb_xml(path: str) -> None:
    Path(path).write_text(_USB_HOSTDEV_XML)


def attach_usb() -> bool:
    """Anexa USB da Epson à VM via virsh attach-device."""
    # Remover usblp do host para liberar o dispositivo
    subprocess.run(["sudo", "rmmod", "usblp"], capture_output=True, timeout=10)
    time.sleep(1)

    if check_usb_attached():
        log.info("USB já está anexado à VM")
        return True

    xml_path = "/tmp/epson_usb_hotplug.xml"
    _write_usb_xml(xml_path)

    rc, _, err = run_virsh(["attach-device", VM_NAME, xml_path, "--live"], timeout=15)
    if rc != 0:
        if "already" in err.lower():
            log.info("USB já estava anexado à VM")
            return True
        log.warning(f"Falha ao anexar USB via virsh: {err}")
        return False

    log.info("USB Epson anexado à VM com sucesso")
    time.sleep(2)
    return True


def force_reattach_usb() -> bool:
    """Desanexa e reaneixa o USB para forçar reenumeração no Windows.
    
    Necessário após restauro de managedsave para evitar status 'Unknown'
    no Device Manager do Windows.
    """
    xml_path = "/tmp/epson_usb_hotplug.xml"
    _write_usb_xml(xml_path)

    # Remover usblp do host
    subprocess.run(["sudo", "rmmod", "usblp"], capture_output=True, timeout=10)
    time.sleep(1)

    # Desanexar se estiver conectado
    if check_usb_attached():
        log.info("Desanexando USB para forçar reenumeração...")
        run_virsh(["detach-device", VM_NAME, xml_path, "--live"], timeout=15)
        time.sleep(4)

    # Reanexar
    log.info("Reanexando USB à VM...")
    rc, _, err = run_virsh(["attach-device", VM_NAME, xml_path, "--live"], timeout=15)
    if rc != 0:
        if "already" in err.lower():
            log.info("USB já estava anexado à VM após reattach")
            return True
        log.warning(f"Falha ao reanexar USB: {err}")
        return False

    log.info("USB Epson reanexado com sucesso (reenumeração forçada)")
    time.sleep(6)  # Aguardar Windows reconhecer e inicializar driver
    return True


def check_usb_attached() -> bool:
    """Verifica se USB Epson está anexado à VM via virsh dumpxml."""
    rc, out, _ = run_virsh(["dumpxml", VM_NAME])
    if rc != 0:
        return False
    return "04b8" in out.lower() and "1120" in out


# ─── WinRM Helper ───────────────────────────────────────────────

def discover_vm_ip() -> str:
    """Descobre IP da VM via MAC no ARP/neighbor table."""
    global VM_IP
    mac_lower = VM_MAC.lower()
    try:
        r = subprocess.run(["ip", "neigh"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            parts = line.split()
            # formato: 192.168.15.7 dev enp1s0 lladdr 08:00:27:00:e9:40 STALE/REACHABLE
            if len(parts) >= 5 and parts[4].lower() == mac_lower:
                ip = parts[0]
                if ip != VM_IP:
                    log.info(f"VM IP atualizado: {VM_IP} -> {ip} (via MAC {VM_MAC})")
                    VM_IP = ip
                return ip
    except Exception as e:
        log.warning(f"Erro ao descobrir IP da VM via MAC: {e}")
    
    # Fallback: usar VM_IP configurado
    log.debug(f"Usando VM_IP configurado: {VM_IP}")
    return VM_IP


def winrm_session():
    """Cria sessão WinRM."""
    import winrm
    ip = discover_vm_ip()
    s = winrm.Session(ip, auth=(VM_USER, VM_PASS), transport="ntlm")
    s.timeout = 60
    return s


def wait_for_winrm(timeout: int = WINRM_TIMEOUT) -> bool:
    """Aguarda WinRM ficar acessível."""
    import socket
    
    discover_vm_ip()
    log.info(f"Aguardando WinRM em {VM_IP}:{WINRM_PORT} (timeout: {timeout}s)...")
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            sock = socket.create_connection((VM_IP, WINRM_PORT), timeout=3)
            sock.close()
            # Porto aberto, testar WinRM de fato
            try:
                s = winrm_session()
                r = s.run_cmd("hostname")
                if r.status_code == 0:
                    hostname = r.std_out.decode().strip()
                    log.info(f"WinRM pronto! Hostname: {hostname}")
                    return True
            except Exception:
                pass
        except (socket.timeout, ConnectionRefusedError, OSError):
            pass
        
        elapsed = int(time.time() - start)
        if elapsed % 10 == 0:
            log.info(f"  Aguardando WinRM... ({elapsed}s)")
        time.sleep(2)
    
    log.error(f"WinRM não ficou pronto em {timeout}s")
    return False


# ─── HTTP File Server ───────────────────────────────────────────
def ensure_http_server() -> bool:
    """Garante que o servidor HTTP em /tmp está rodando."""
    import socket
    try:
        sock = socket.create_connection(("127.0.0.1", HTTP_PORT), timeout=2)
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        pass
    
    log.info(f"Iniciando HTTP server na porta {HTTP_PORT}...")
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", str(HTTP_PORT)],
        cwd="/tmp",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    state["http_server_pid"] = proc.pid
    time.sleep(1)
    return True


# ─── Impressão ──────────────────────────────────────────────────
def transfer_and_print(local_path: str, copies: int = 1) -> dict:
    """Transfere arquivo para VM e imprime."""
    orig_filename = os.path.basename(local_path)
    
    # Sanitizar nomes com espaços/caracteres especiais (ex: WhatsApp Image...)
    safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', orig_filename)
    filename = safe_filename
    
    # Garantir que arquivo está em /tmp para o HTTP server
    tmp_path = f"/tmp/{safe_filename}"
    if os.path.abspath(local_path) != os.path.abspath(tmp_path):
        shutil.copy2(local_path, tmp_path)
    
    # Garantir HTTP server
    ensure_http_server()
    
    # Baixar na VM via curl — usar nome seguro sem espaços
    s = winrm_session()
    vm_path = f"C:\\\\temp\\\\{safe_filename}"
    url_filename = urlquote(safe_filename)
    
    log.info(f"Transferindo {orig_filename} -> {safe_filename} para VM...")
    r = s.run_cmd(f'curl.exe -sf -o "C:\\temp\\{safe_filename}" "http://192.168.15.2:{HTTP_PORT}/{url_filename}"')
    if r.status_code != 0:
        raise RuntimeError(f"Falha no download: {r.std_err.decode()}")
    
    # Verificar arquivo na VM
    r = s.run_cmd(f'dir "C:\\temp\\{filename}"')
    log.info(f"Arquivo na VM: {r.std_out.decode().strip()}")
    
    # Garantir que o script de impressão PS1 está na VM
    r = s.run_cmd('if not exist C:\\temp\\print_image.ps1 curl.exe -s -o C:\\temp\\print_image.ps1 http://192.168.15.2:{0}/print_image.ps1'.format(HTTP_PORT))

    # Garantir impressora online (evita WorkOffline=True após restore de managedsave)
    r_online = s.run_ps(
        f'$wmi = Get-WmiObject Win32_Printer -Filter "Name=\'{PRINTER_NAME}\'";'
        f'if ($wmi.WorkOffline) {{ $wmi.WorkOffline = $false; $wmi.Put() | Out-Null;'
        f' Write-Host "Impressora colocada online" }} else {{ Write-Host "Impressora ja online" }}'
    )
    log.info(f"Status online: {r_online.std_out.decode().strip()}")
    
    # Imprimir via .NET PrintDocument (funciona em sessão de serviço WinRM)
    log.info(f"Enviando impressão: {filename} → {PRINTER_NAME} (cópias: {copies})")
    
    for i in range(copies):
        r = s.run_ps(
            f'Set-ExecutionPolicy Bypass -Scope Process -Force; '
            f'& C:\\temp\\print_image.ps1 "C:\\temp\\{filename}" "{PRINTER_NAME}"'
        )
        stdout = r.std_out.decode().strip()
        stderr = r.std_err.decode().strip()
        log.info(f"  Cópia {i+1}: {stdout}")
        if r.status_code != 0 and "ERRO:" in stdout:
            raise RuntimeError(f"Falha na impressão: {stdout} {stderr}")
    
    # Verificar fila
    time.sleep(2)
    r = s.run_ps(
        f'Get-PrintJob -PrinterName "{PRINTER_NAME}" | '
        'Select-Object Id,DocumentName,JobStatus | Format-Table -AutoSize'
    )
    queue = r.std_out.decode().strip()
    log.info(f"Fila de impressão:\n{queue}")
    
    return {
        "status": "sent",
        "filename": filename,
        "copies": copies,
        "printer": PRINTER_NAME,
        "queue": queue,
    }


# ─── VM Lifecycle completo ──────────────────────────────────────
async def ensure_vm_ready() -> bool:
    """Garante que a VM está ligada, com USB e WinRM prontos."""
    vm_state = get_vm_state()
    state["vm_status"] = vm_state
    
    if vm_state != "running":
        state["vm_status"] = "starting"
        log.info(f"VM não está rodando (estado: {vm_state}), iniciando...")
        
        loop = asyncio.get_event_loop()
        started = await loop.run_in_executor(None, start_vm)
        if not started:
            state["vm_status"] = "error"
            raise RuntimeError("Falha ao iniciar VM")
        
        state["startup_time"] = datetime.now(timezone.utc).isoformat()
        
        # Aguardar WinRM
        ready = await loop.run_in_executor(None, wait_for_winrm)
        if not ready:
            state["vm_status"] = "error"
            raise RuntimeError("WinRM não ficou pronto após iniciar VM")
        
        # Forçar reattach USB para garantir reenumeração correta no Windows
        # (evita status 'Unknown' após restauro de managedsave)
        await loop.run_in_executor(None, force_reattach_usb)
        # Aguardar Windows reconhecer driver USB
        await asyncio.sleep(3)
    else:
        # VM já rodando, verificar WinRM
        loop = asyncio.get_event_loop()
        ready = await loop.run_in_executor(None, lambda: wait_for_winrm(timeout=WINRM_TIMEOUT))
        if not ready:
            raise RuntimeError("VM rodando mas WinRM não responde")
        
        # Verificar USB
        if not check_usb_attached():
            log.info("USB não anexado, anexando...")
            await loop.run_in_executor(None, attach_usb)
            await asyncio.sleep(3)
    
    state["vm_status"] = "running"
    return True


def schedule_idle_shutdown():
    """Agenda desligamento da VM após IDLE_TIMEOUT."""
    global shutdown_timer
    
    if shutdown_timer:
        shutdown_timer.cancel()
    
    shutdown_time = time.time() + IDLE_TIMEOUT
    state["idle_shutdown_at"] = datetime.fromtimestamp(
        shutdown_time, tz=timezone.utc
    ).isoformat()
    
    log.info(f"VM será desligada em {IDLE_TIMEOUT}s se não houver atividade")
    
    def do_shutdown():
        vm_st = get_vm_state()
        if vm_st == "running":
            log.info(f"Idle timeout ({IDLE_TIMEOUT}s) atingido, salvando estado da VM...")
            stop_vm(save_state=True)
            state["vm_status"] = "saved"
            state["idle_shutdown_at"] = None
            log.info("VM salva com sucesso (savestate)")
        else:
            log.info(f"VM já não está rodando ({vm_st}), nada a fazer")
    
    shutdown_timer = threading.Timer(IDLE_TIMEOUT, do_shutdown)
    shutdown_timer.daemon = True
    shutdown_timer.start()


# ─── Scanner SANE ───────────────────────────────────────────────
def detach_usb_from_vm() -> bool:
    """Libera USB da Epson da VM para o host Linux via virsh detach-device."""
    if get_vm_state() != "running":
        log.info("VM não está rodando, USB já está no host")
        return True

    if not check_usb_attached():
        log.info("USB Epson não está na VM, já está no host")
        return True

    xml_path = "/tmp/epson_usb_hotplug.xml"
    _write_usb_xml(xml_path)

    log.info("Liberando USB da VM para o host via virsh detach-device...")
    rc, _, err = run_virsh(["detach-device", VM_NAME, xml_path, "--live"], timeout=15)
    if rc != 0 and "not found" not in err.lower() and "not attached" not in err.lower():
        log.warning(f"Falha ao liberar USB: {err}")
        return False

    time.sleep(2)
    log.info("USB liberado da VM para o host")
    return True


def find_sane_device() -> Optional[str]:
    """Descobre o dispositivo SANE atual via scanimage -L."""
    try:
        r = subprocess.run(
            ["scanimage", "-L"],
            capture_output=True, text=True, timeout=15
        )
        for line in r.stdout.splitlines() + r.stderr.splitlines():
            # formato: device `epson2:libusb:001:010' is a Epson PID 1120 flatbed scanner
            if SCAN_USB_PID in line and "epson" in line.lower():
                # Extrair device name entre ` e '
                start = line.find("`")
                end = line.find("'")
                if start >= 0 and end > start:
                    dev = line[start + 1:end]
                    log.info(f"Dispositivo SANE encontrado: {dev}")
                    return dev
        log.warning(f"Nenhum dispositivo SANE encontrado (saída: {r.stdout} {r.stderr})")
        return None
    except Exception as e:
        log.error(f"Erro ao buscar dispositivo SANE: {e}")
        return None


def ensure_usb_on_host() -> bool:
    """Garante que o USB da Epson está acessível no host Linux."""
    # Carregar módulo usblp para o scanner funcionar
    subprocess.run(["sudo", "modprobe", "usblp"], capture_output=True, timeout=10)
    time.sleep(1)

    # Verificar se USB está no host
    try:
        r = subprocess.run(
            ["lsusb", "-d", f"{SCAN_USB_VID}:{SCAN_USB_PID}"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0 and r.stdout.strip():
            log.info(f"USB Epson no host: {r.stdout.strip()}")
            return True
    except Exception:
        pass

    log.warning("USB Epson não encontrada no host")
    return False


def do_scan(
    resolution: int = SCAN_DEFAULT_RESOLUTION,
    fmt: str = SCAN_DEFAULT_FORMAT,
    mode: str = SCAN_DEFAULT_MODE,
) -> str:
    """Executa scan via WIA (Windows) ou SANE (Linux fallback)."""
    os.makedirs(SCAN_DIR, exist_ok=True)

    ext_map = {"jpeg": "jpg", "png": "png", "tiff": "tif", "pnm": "pnm", "pdf": "pdf", "bmp": "bmp"}
    ext = ext_map.get(fmt, fmt)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(SCAN_DIR, f"scan_{timestamp}.{ext}")

    if SCAN_METHOD == "wia":
        return do_scan_wia(resolution, fmt, mode, output_file)
    else:
        return do_scan_sane(resolution, fmt, mode, output_file)


def do_scan_wia(
    resolution: int, fmt: str, mode: str, output_file: str
) -> str:
    """Executa scan via WIA (Windows Image Acquisition) na VM Windows."""
    # Mapear modo para WIA Data Type: 0=Default, 2=Grayscale, 3=Color, 4=B&W
    wia_mode_map = {"Color": 3, "Gray": 2, "Lineart": 4}
    wia_data_type = wia_mode_map.get(mode, 3)

    # Mapear formato para WIA format GUID
    wia_format_map = {
        "jpeg": "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}",
        "png":  "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}",
        "bmp":  "{B96B3CAB-0728-11D3-9D7B-0000F81EF32E}",
        "tiff": "{B96B3CB1-0728-11D3-9D7B-0000F81EF32E}",
    }
    # WIA drivers often ignore format GUID and always output BMP.
    # Always transfer as BMP and convert to requested format via PIL afterwards.
    use_fmt = "bmp"
    wia_guid = wia_format_map["bmp"]

    # Calcular extent (pixels) para o resolution desejado (A4 = 8.27 x 11.69 inches)
    h_extent = int(8.27 * resolution)
    v_extent = int(11.69 * resolution)

    vm_file = "C:\\temp\\scan_wia.bmp"

    ps_script = f"""$ErrorActionPreference = "Stop"
$dm = New-Object -ComObject WIA.DeviceManager
$dev = $dm.DeviceInfos.Item(1).Connect()
$item = $dev.Items.Item(1)
$item.Properties.Item("Horizontal Resolution").Value = {resolution}
$item.Properties.Item("Vertical Resolution").Value = {resolution}
$item.Properties.Item("Horizontal Extent").Value = {h_extent}
$item.Properties.Item("Vertical Extent").Value = {v_extent}
$item.Properties.Item("Data Type").Value = {wia_data_type}
$img = $item.Transfer("{wia_guid}")
if (Test-Path "{vm_file}") {{ Remove-Item "{vm_file}" }}
$img.SaveFile("{vm_file}")
$bytes = [System.IO.File]::ReadAllBytes("{vm_file}")
[System.Convert]::ToBase64String($bytes)
"""

    log.info(f"Scan WIA: {resolution}dpi, {mode}, fmt={use_fmt}, extent={h_extent}x{v_extent}")

    s = winrm_session()
    r = s.run_ps(ps_script)
    stdout = r.std_out.decode().strip()
    stderr = r.std_err.decode().strip()

    # Verificar erro (ignorar mensagens CLIXML de "Preparing modules")
    if r.status_code != 0 or (not stdout and "CLIXML" not in stderr):
        raise RuntimeError(f"WIA scan falhou (rc={r.status_code}): {stderr[:300]}")

    # Decodificar base64 e salvar
    try:
        img_data = base64.b64decode(stdout)
    except Exception as e:
        raise RuntimeError(f"Erro ao decodificar imagem base64: {e}")

    if len(img_data) < 100:
        raise RuntimeError(f"Dados de scan muito pequenos ({len(img_data)} bytes)")

    # Converter de BMP para o formato solicitado via PIL
    if fmt in ("jpeg", "png", "tiff") and fmt != "bmp":
        try:
            from PIL import Image
            import io
            pil_img = Image.open(io.BytesIO(img_data))
            buf = io.BytesIO()
            pil_fmt_map = {"jpeg": "JPEG", "png": "PNG", "tiff": "TIFF"}
            pil_fmt = pil_fmt_map.get(fmt, "JPEG")
            save_kwargs = {"dpi": (resolution, resolution)}
            if pil_fmt == "JPEG":
                save_kwargs["quality"] = 90
            pil_img.save(buf, format=pil_fmt, **save_kwargs)
            img_data = buf.getvalue()
        except ImportError:
            log.warning("PIL não disponível, salvando em formato WIA nativo")
            output_file = output_file.rsplit(".", 1)[0] + f".{use_fmt}"

    with open(output_file, "wb") as f:
        f.write(img_data)

    size_kb = len(img_data) / 1024
    log.info(f"Scan WIA concluído: {output_file} ({size_kb:.1f} KB)")
    return output_file


def do_scan_sane(
    resolution: int, fmt: str, mode: str, output_file: str
) -> str:
    """Executa scan via SANE (scanimage) no host Linux."""
    device = find_sane_device()
    if not device:
        raise RuntimeError("Dispositivo SANE não encontrado. USB pode não estar no host.")

    cmd = [
        "scanimage", "-d", device,
        "--resolution", str(resolution),
        "--mode", mode,
        f"--format={fmt}",
        "-o", output_file,
    ]

    log.info(f"Executando scan SANE: {' '.join(cmd)}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError(f"scanimage falhou (rc={r.returncode}): {r.stderr}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("Scan timeout (120s)")

    if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
        raise RuntimeError(f"Arquivo de scan vazio ou não criado: {output_file}")

    size_kb = os.path.getsize(output_file) / 1024
    log.info(f"Scan SANE concluído: {output_file} ({size_kb:.1f} KB)")
    return output_file


def reattach_usb_to_vm() -> bool:
    """Reaproveita USB para a VM (se ela estiver rodando)."""
    if get_vm_state() != "running":
        log.info("VM não está rodando, USB permanece no host")
        return True

    # Remover usblp do host para a VM poder capturar
    subprocess.run(["sudo", "rmmod", "usblp"], capture_output=True, timeout=10)
    time.sleep(1)

    return attach_usb()


# ─── eSCL (AirScan) Protocol ───────────────────────────────────
def escl_scanner_capabilities_xml() -> str:
    """Gera XML de ScannerCapabilities para protocolo eSCL."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<scan:ScannerCapabilities xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm" xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">
  <pwg:Version>2.63</pwg:Version>
  <pwg:MakeAndModel>EPSON L380 Series</pwg:MakeAndModel>
  <pwg:SerialNumber>L380-homelab</pwg:SerialNumber>
  <scan:UUID>{ESCL_UUID}</scan:UUID>
  <scan:AdminURI>http://192.168.15.2:{SERVICE_PORT}/</scan:AdminURI>
  <scan:Platen>
    <scan:PlatenInputCaps>
      <scan:MinWidth>{ESCL_MIN_WIDTH}</scan:MinWidth>
      <scan:MaxWidth>{ESCL_MAX_WIDTH}</scan:MaxWidth>
      <scan:MinHeight>{ESCL_MIN_HEIGHT}</scan:MinHeight>
      <scan:MaxHeight>{ESCL_MAX_HEIGHT}</scan:MaxHeight>
      <scan:MaxScanRegions>1</scan:MaxScanRegions>
      <scan:SettingProfiles>
        <scan:SettingProfile>
          <scan:ColorModes>
            <scan:ColorMode>RGB24</scan:ColorMode>
            <scan:ColorMode>Grayscale8</scan:ColorMode>
            <scan:ColorMode>BlackAndWhite1</scan:ColorMode>
          </scan:ColorModes>
          <scan:DocumentFormats>
            <pwg:DocumentFormat>image/jpeg</pwg:DocumentFormat>
            <pwg:DocumentFormat>image/png</pwg:DocumentFormat>
            <scan:DocumentFormatExt>image/jpeg</scan:DocumentFormatExt>
            <scan:DocumentFormatExt>image/png</scan:DocumentFormatExt>
          </scan:DocumentFormats>
          <scan:SupportedResolutions>
            <scan:DiscreteResolutions>
              <scan:DiscreteResolution><scan:XResolution>75</scan:XResolution><scan:YResolution>75</scan:YResolution></scan:DiscreteResolution>
              <scan:DiscreteResolution><scan:XResolution>150</scan:XResolution><scan:YResolution>150</scan:YResolution></scan:DiscreteResolution>
              <scan:DiscreteResolution><scan:XResolution>300</scan:XResolution><scan:YResolution>300</scan:YResolution></scan:DiscreteResolution>
              <scan:DiscreteResolution><scan:XResolution>600</scan:XResolution><scan:YResolution>600</scan:YResolution></scan:DiscreteResolution>
              <scan:DiscreteResolution><scan:XResolution>1200</scan:XResolution><scan:YResolution>1200</scan:YResolution></scan:DiscreteResolution>
            </scan:DiscreteResolutions>
          </scan:SupportedResolutions>
          <scan:ColorSpaces>
            <scan:ColorSpace>sRGB</scan:ColorSpace>
          </scan:ColorSpaces>
        </scan:SettingProfile>
      </scan:SettingProfiles>
      <scan:SupportedIntents>
        <scan:Intent>Document</scan:Intent>
        <scan:Intent>TextAndGraphic</scan:Intent>
        <scan:Intent>Photo</scan:Intent>
        <scan:Intent>Preview</scan:Intent>
      </scan:SupportedIntents>
    </scan:PlatenInputCaps>
  </scan:Platen>
</scan:ScannerCapabilities>"""


def escl_scanner_status_xml() -> str:
    """Gera XML de ScannerStatus para protocolo eSCL."""
    processing = any(j["state"] == "Processing" for j in escl_jobs.values())
    state_str = "Processing" if processing else "Idle"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<scan:ScannerStatus xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm" xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">
  <pwg:Version>2.63</pwg:Version>
  <pwg:State>{state_str}</pwg:State>
  <pwg:StateReasons>
    <pwg:StateReason>None</pwg:StateReason>
  </pwg:StateReasons>
</scan:ScannerStatus>"""


def parse_escl_scan_settings(xml_body: str) -> dict:
    """Parse eSCL ScanSettings XML em parâmetros de scan."""
    settings = {"resolution": 300, "format": "jpeg", "mode": "Color"}
    try:
        root = ET.fromstring(xml_body)
        ns = {
            "scan": "http://schemas.hp.com/imaging/escl/2011/05/03",
            "pwg": "http://www.pwg.org/schemas/2010/12/sm",
        }
        xres = root.find(".//scan:XResolution", ns)
        if xres is not None and xres.text:
            settings["resolution"] = int(xres.text)
        cm = root.find(".//scan:ColorMode", ns)
        if cm is not None and cm.text:
            mode_map = {"RGB24": "Color", "Grayscale8": "Gray", "BlackAndWhite1": "Lineart"}
            settings["mode"] = mode_map.get(cm.text, "Color")
        df = root.find(".//pwg:DocumentFormat", ns)
        if df is None:
            df = root.find(".//scan:DocumentFormatExt", ns)
        if df is not None and df.text:
            fmt_map = {"image/jpeg": "jpeg", "image/png": "png", "image/tiff": "tiff"}
            settings["format"] = fmt_map.get(df.text, "jpeg")
    except Exception as e:
        log.warning(f"Erro ao parser eSCL ScanSettings: {e}, usando padrões")
    return settings


# ─── FastAPI App ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup e shutdown."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(SCAN_DIR, exist_ok=True)
    state["vm_status"] = get_vm_state()
    log.info(f"Print & Scan On-Demand Service iniciado — porta {SERVICE_PORT}")
    log.info(f"VM: {VM_NAME} | Impressora: {PRINTER_NAME}")
    log.info(f"Scanner: method={SCAN_METHOD} (SANE fallback={SCAN_BACKEND}, VID={SCAN_USB_VID} PID={SCAN_USB_PID})")
    log.info(f"eSCL AirScan: /eSCL/ (UUID={ESCL_UUID})")
    log.info(f"Idle timeout: {IDLE_TIMEOUT}s | VM estado: {state['vm_status']}")
    yield
    # Cleanup
    global shutdown_timer
    if shutdown_timer:
        shutdown_timer.cancel()
    log.info("Serviço encerrado")


app = FastAPI(
    title="Print & Scan On-Demand Service",
    description="Gerencia VM Windows para impressão e scanner SANE para Epson L380",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "print-ondemand",
        "vm_name": VM_NAME,
        "vm_status": state["vm_status"],
        "printer": PRINTER_NAME,
        "uptime": time.process_time(),
    }


@app.get("/metrics")
async def metrics():
    """Métricas Prometheus."""
    vm_running = 1 if state["vm_status"] == "running" else 0
    lines = [
        "# HELP print_ondemand_jobs_total Total de jobs de impressão",
        "# TYPE print_ondemand_jobs_total counter",
        f'print_ondemand_jobs_total {state["jobs_total"]}',
        "# HELP print_ondemand_jobs_completed Jobs completados",
        "# TYPE print_ondemand_jobs_completed counter",
        f'print_ondemand_jobs_completed {state["jobs_completed"]}',
        "# HELP print_ondemand_jobs_failed Jobs com falha",
        "# TYPE print_ondemand_jobs_failed counter",
        f'print_ondemand_jobs_failed {state["jobs_failed"]}',
        "# HELP print_ondemand_vm_running VM está rodando",
        "# TYPE print_ondemand_vm_running gauge",
        f'print_ondemand_vm_running {vm_running}',
        "# HELP print_ondemand_scans_total Total de scans",
        "# TYPE print_ondemand_scans_total counter",
        f'print_ondemand_scans_total {state["scans_total"]}',
        "# HELP print_ondemand_scans_completed Scans completados",
        "# TYPE print_ondemand_scans_completed counter",
        f'print_ondemand_scans_completed {state["scans_completed"]}',
        "# HELP print_ondemand_scans_failed Scans com falha",
        "# TYPE print_ondemand_scans_failed counter",
        f'print_ondemand_scans_failed {state["scans_failed"]}',
    ]
    return "\n".join(lines) + "\n"


@app.get("/status")
async def status():
    """Status completo do serviço."""
    state["vm_status"] = get_vm_state()
    return {
        **state,
        "config": {
            "vm_name": VM_NAME,
            "vm_ip": VM_IP,
            "printer": PRINTER_NAME,
            "idle_timeout": IDLE_TIMEOUT,
            "usb_uuid": USB_UUID,
        }
    }


@app.post("/print")
async def print_file(
    file: Optional[UploadFile] = File(None),
    path: Optional[str] = Form(None),
    copies: int = Form(1),
):
    """
    Imprime um arquivo.
    
    - file: upload multipart do arquivo
    - path: caminho local no homelab (ex: /tmp/foto.jpg)
    - copies: número de cópias (padrão: 1)
    """
    if not file and not path:
        raise HTTPException(400, "Forneça 'file' (upload) ou 'path' (caminho local)")
    
    state["jobs_total"] += 1
    job_id = state["jobs_total"]
    
    try:
        # Resolver arquivo local
        if file:
            local_path = os.path.join(TEMP_DIR, file.filename)
            with open(local_path, "wb") as f:
                content = await file.read()
                f.write(content)
            # Copiar para /tmp para o HTTP server
            shutil.copy2(local_path, f"/tmp/{file.filename}")
            local_path = f"/tmp/{file.filename}"
        else:
            local_path = path
            if not os.path.exists(local_path):
                raise HTTPException(404, f"Arquivo não encontrado: {path}")
        
        state["current_job"] = {
            "id": job_id,
            "file": os.path.basename(local_path),
            "started": datetime.now(timezone.utc).isoformat(),
        }
        
        # Garantir VM pronta
        async with vm_lock:
            await ensure_vm_ready()
        
        # Imprimir
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: transfer_and_print(local_path, copies)
        )
        
        state["jobs_completed"] += 1
        state["last_activity"] = datetime.now(timezone.utc).isoformat()
        state["current_job"] = None
        
        # Agendar shutdown por ociosidade
        schedule_idle_shutdown()
        
        return {
            "job_id": job_id,
            "result": result,
            "vm_shutdown_in": f"{IDLE_TIMEOUT}s",
        }
    
    except Exception as e:
        state["jobs_failed"] += 1
        state["current_job"] = None
        log.error(f"Job {job_id} falhou: {e}")
        raise HTTPException(500, f"Falha na impressão: {str(e)}")


@app.post("/scan")
async def scan_document(
    resolution: int = Query(SCAN_DEFAULT_RESOLUTION, ge=75, le=1200, description="DPI (75-1200)"),
    format: str = Query(SCAN_DEFAULT_FORMAT, description="Formato: jpeg, png, tiff, pnm"),
    mode: str = Query(SCAN_DEFAULT_MODE, description="Modo: Color, Gray, Lineart"),
):
    """
    Digitaliza documento.

    WIA (padrão): usa o scanner via Windows VM + WinRM.
    SANE (fallback): libera USB da VM, escaneia no host Linux, reaproveita USB.
    """
    async with scan_lock:
        state["scans_total"] += 1
        scan_id = state["scans_total"]
        state["current_scan"] = {
            "id": scan_id,
            "resolution": resolution,
            "format": format,
            "mode": mode,
            "started": datetime.now(timezone.utc).isoformat(),
        }

        vm_was_running = get_vm_state() == "running"
        usb_released = False

        try:
            if SCAN_METHOD == "wia":
                # Para WIA, a VM PRECISA estar rodando com USB
                await ensure_vm_ready()
                schedule_idle_shutdown()
            else:
                # Para SANE, liberar USB da VM para o host
                if vm_was_running:
                    log.info("VM rodando — liberando USB para scan SANE...")
                    loop = asyncio.get_event_loop()
                    released = await loop.run_in_executor(None, detach_usb_from_vm)
                    if not released:
                        raise RuntimeError("Não foi possível liberar USB da VM")
                    usb_released = True
                    await asyncio.sleep(2)
                loop = asyncio.get_event_loop()
                host_ok = await loop.run_in_executor(None, ensure_usb_on_host)
                if not host_ok:
                    raise RuntimeError("USB Epson não disponível no host")

            # Executar scan
            loop = asyncio.get_event_loop()
            output_file = await loop.run_in_executor(
                None, lambda: do_scan(resolution, format, mode)
            )

            state["scans_completed"] += 1
            state["last_scan"] = datetime.now(timezone.utc).isoformat()
            state["current_scan"] = None

            media_types = {
                "jpeg": "image/jpeg", "png": "image/png",
                "tiff": "image/tiff", "pnm": "image/x-portable-anymap",
                "pdf": "application/pdf", "bmp": "image/bmp",
            }
            media = media_types.get(format, "application/octet-stream")
            fname = os.path.basename(output_file)

            return FileResponse(
                output_file,
                media_type=media,
                filename=fname,
                headers={"X-Scan-Id": str(scan_id)},
            )

        except Exception as e:
            state["scans_failed"] += 1
            state["current_scan"] = None
            log.error(f"Scan {scan_id} falhou: {e}")
            raise HTTPException(500, f"Falha no scan: {str(e)}")

        finally:
            if usb_released and vm_was_running and get_vm_state() == "running":
                log.info("Reanexando USB à VM...")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, reattach_usb_to_vm)


@app.get("/scan/preview")
async def scan_preview():
    """Scan rápido para preview (150dpi, JPEG, modo Color)."""
    async with scan_lock:
        state["scans_total"] += 1
        scan_id = state["scans_total"]

        vm_was_running = get_vm_state() == "running"
        usb_released = False

        try:
            if SCAN_METHOD == "wia":
                await ensure_vm_ready()
                schedule_idle_shutdown()
            else:
                if vm_was_running:
                    loop = asyncio.get_event_loop()
                    released = await loop.run_in_executor(None, detach_usb_from_vm)
                    if not released:
                        raise RuntimeError("Não foi possível liberar USB da VM")
                    usb_released = True
                    await asyncio.sleep(2)
                loop = asyncio.get_event_loop()
                host_ok = await loop.run_in_executor(None, ensure_usb_on_host)
                if not host_ok:
                    raise RuntimeError("USB Epson não disponível no host")

            loop = asyncio.get_event_loop()
            output_file = await loop.run_in_executor(
                None, lambda: do_scan(150, "jpeg", "Color")
            )

            state["scans_completed"] += 1
            state["last_scan"] = datetime.now(timezone.utc).isoformat()

            return FileResponse(
                output_file,
                media_type="image/jpeg",
                filename=os.path.basename(output_file),
                headers={"X-Scan-Id": str(scan_id)},
            )

        except Exception as e:
            state["scans_failed"] += 1
            log.error(f"Preview scan {scan_id} falhou: {e}")
            raise HTTPException(500, f"Falha no preview: {str(e)}")

        finally:
            if usb_released and vm_was_running and get_vm_state() == "running":
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, reattach_usb_to_vm)


# ─── eSCL Routes ────────────────────────────────────────────────
@app.get("/eSCL/ScannerCapabilities")
async def escl_capabilities():
    """eSCL: Retorna capacidades do scanner."""
    return Response(content=escl_scanner_capabilities_xml(), media_type="text/xml")


@app.get("/eSCL/ScannerStatus")
async def escl_status():
    """eSCL: Retorna estado do scanner."""
    return Response(content=escl_scanner_status_xml(), media_type="text/xml")


@app.post("/eSCL/ScanJobs")
async def escl_create_job(request: Request):
    """eSCL: Cria um job de digitalização."""
    global escl_job_counter
    escl_job_counter += 1
    job_id = str(escl_job_counter)

    body = await request.body()
    settings = parse_escl_scan_settings(body.decode("utf-8", errors="replace"))

    escl_jobs[job_id] = {
        "state": "Pending",
        "file": None,
        "settings": settings,
        "created": datetime.now(timezone.utc).isoformat(),
    }

    log.info(f"eSCL Job {job_id} criado: res={settings['resolution']} "
             f"fmt={settings['format']} mode={settings['mode']}")

    # eSCL spec requires absolute URL in Location header
    # SANE escl backend requires capitalized "Location" header (case-sensitive bug)
    host = request.headers.get("host", request.base_url.netloc)
    scheme = request.headers.get("x-forwarded-proto", str(request.url.scheme))
    location_url = f"{scheme}://{host}/eSCL/ScanJobs/{job_id}"
    # Use raw ASGI response to control header capitalization
    from starlette.responses import Response as StarletteResponse
    resp = StarletteResponse(status_code=201, content="")
    resp.headers.raw.append((b"Location", location_url.encode()))
    return resp


@app.get("/eSCL/ScanJobs/{job_id}/NextDocument")
async def escl_next_document(job_id: str):
    """eSCL: Executa scan e retorna documento digitalizado."""
    if job_id not in escl_jobs:
        raise HTTPException(404, "Job not found")

    job = escl_jobs[job_id]

    # Se já escaneou e arquivo existe, retorna cached
    if job["state"] == "Completed" and job.get("file") and os.path.exists(job["file"]):
        fmt = job["settings"]["format"]
        media = {"jpeg": "image/jpeg", "png": "image/png", "tiff": "image/tiff"}.get(fmt, "application/octet-stream")
        result_file = job["file"]
        del escl_jobs[job_id]
        return FileResponse(result_file, media_type=media)

    # Executar scan
    job["state"] = "Processing"
    settings = job["settings"]

    async with scan_lock:
        vm_was_running = get_vm_state() == "running"
        usb_released = False

        try:
            if SCAN_METHOD == "wia":
                await ensure_vm_ready()
                schedule_idle_shutdown()
            else:
                if vm_was_running:
                    loop = asyncio.get_event_loop()
                    released = await loop.run_in_executor(None, detach_usb_from_vm)
                    if not released:
                        raise RuntimeError("Não foi possível liberar USB da VM")
                    usb_released = True
                    await asyncio.sleep(2)
                loop = asyncio.get_event_loop()
                host_ok = await loop.run_in_executor(None, ensure_usb_on_host)
                if not host_ok:
                    raise RuntimeError("USB Epson não disponível no host")

            loop = asyncio.get_event_loop()
            output_file = await loop.run_in_executor(
                None,
                lambda: do_scan(settings["resolution"], settings["format"], settings["mode"])
            )

            job["state"] = "Completed"
            job["file"] = output_file
            state["scans_completed"] += 1
            state["scans_total"] += 1
            state["last_scan"] = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            job["state"] = "Canceled"
            state["scans_failed"] += 1
            state["scans_total"] += 1
            log.error(f"eSCL Job {job_id} falhou: {e}")
            raise HTTPException(500, str(e))

        finally:
            if usb_released and vm_was_running and get_vm_state() == "running":
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, reattach_usb_to_vm)

    # Retorna imagem escaneada
    fmt = settings["format"]
    media = {"jpeg": "image/jpeg", "png": "image/png", "tiff": "image/tiff"}.get(fmt, "application/octet-stream")
    result_file = job["file"]
    del escl_jobs[job_id]
    return FileResponse(result_file, media_type=media)


@app.delete("/eSCL/ScanJobs/{job_id}")
async def escl_delete_job(job_id: str):
    """eSCL: Cancela/remove job de scan."""
    if job_id in escl_jobs:
        job = escl_jobs.pop(job_id)
        if job.get("file") and os.path.exists(job["file"]):
            os.remove(job["file"])
    return Response(status_code=200)


@app.post("/vm/start")
async def vm_start():
    """Força start da VM."""
    async with vm_lock:
        await ensure_vm_ready()
    schedule_idle_shutdown()
    return {"status": "running", "vm": VM_NAME}


@app.post("/vm/stop")
async def vm_stop(save: bool = True):
    """Para a VM (save=true para savestate, false para ACPI shutdown)."""
    global shutdown_timer
    if shutdown_timer:
        shutdown_timer.cancel()
        shutdown_timer = None
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: stop_vm(save_state=save))
    state["vm_status"] = get_vm_state()
    state["idle_shutdown_at"] = None
    
    return {"status": state["vm_status"], "vm": VM_NAME}


@app.post("/vm/extend")
async def vm_extend(minutes: int = 5):
    """Estende o timeout de ociosidade."""
    global IDLE_TIMEOUT
    IDLE_TIMEOUT = minutes * 60
    schedule_idle_shutdown()
    return {"idle_timeout": IDLE_TIMEOUT, "shutdown_at": state["idle_shutdown_at"]}


# ─── Main ───────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "print_ondemand:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        log_level="info",
    )
