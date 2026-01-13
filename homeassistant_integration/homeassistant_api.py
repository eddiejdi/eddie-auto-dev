#!/usr/bin/env python3
"""
Home Assistant API Client
Permite que IAs controlem dispositivos do Home Assistant
"""

import os
import json
import requests
from dataclasses import dataclass

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

@dataclass
class HAConfig:
    url: str = "http://localhost:8123"
    token: str = ""
    
    @classmethod
    def load(cls):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                return cls(**json.load(f))
        return cls()
    
    def save(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({"url": self.url, "token": self.token}, f, indent=2)


class HomeAssistantAPI:
    def __init__(self, url=None, token=None):
        config = HAConfig.load()
        self.url = (url or config.url).rstrip("/")
        self.token = token or config.token
        self.headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
    
    def _request(self, method, endpoint, data=None):
        try:
            r = requests.request(method, f"{self.url}/api/{endpoint}", headers=self.headers, json=data, timeout=10)
            r.raise_for_status()
            return r.json() if r.text else {}
        except Exception as e:
            return {"error": str(e)}
    
    def check_connection(self):
        try:
            r = requests.get(f"{self.url}/api/", headers=self.headers, timeout=5)
            if r.status_code == 200:
                return {"status": "connected", "message": r.json().get("message", "OK")}
            if r.status_code == 401:
                return {"status": "unauthorized", "message": "Token invalido ou nao configurado"}
            return {"status": "error", "message": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"status": "offline", "message": str(e)}
    
    def get_config(self):
        return self._request("GET", "config")
    
    def get_states(self):
        r = self._request("GET", "states")
        return r if isinstance(r, list) else []
    
    def get_state(self, entity_id):
        return self._request("GET", f"states/{entity_id}")
    
    def get_devices_by_domain(self, domain):
        return [s for s in self.get_states() if s.get("entity_id", "").startswith(f"{domain}.")]
    
    def get_lights(self):
        return self.get_devices_by_domain("light")
    
    def get_switches(self):
        return self.get_devices_by_domain("switch")
    
    def get_climate(self):
        return self.get_devices_by_domain("climate")
    
    def call_service(self, domain, service, entity_id=None, **kwargs):
        data = {"entity_id": entity_id} if entity_id else {}
        data.update(kwargs)
        return self._request("POST", f"services/{domain}/{service}", data)
    
    def turn_on(self, entity_id, **kwargs):
        domain = entity_id.split(".")[0]
        return self.call_service(domain, "turn_on", entity_id, **kwargs)
    
    def turn_off(self, entity_id):
        domain = entity_id.split(".")[0]
        return self.call_service(domain, "turn_off", entity_id)
    
    def toggle(self, entity_id):
        domain = entity_id.split(".")[0]
        return self.call_service(domain, "toggle", entity_id)
    
    def set_climate_temperature(self, entity_id, temp):
        return self.call_service("climate", "set_temperature", entity_id, temperature=temp)
    
    def activate_scene(self, entity_id):
        return self.call_service("scene", "turn_on", entity_id)
    
    def run_script(self, entity_id):
        return self.call_service("script", "turn_on", entity_id)
    
    def get_friendly_name(self, entity):
        return entity.get("attributes", {}).get("friendly_name", entity.get("entity_id", ""))
    
    def summarize_devices(self):
        states = self.get_states()
        summary = {"total": len(states), "by_domain": {}, "devices": []}
        for s in states:
            eid = s.get("entity_id", "")
            domain = eid.split(".")[0] if "." in eid else "unknown"
            summary["by_domain"][domain] = summary["by_domain"].get(domain, 0) + 1
            summary["devices"].append({
                "entity_id": eid,
                "name": self.get_friendly_name(s),
                "state": s.get("state"),
                "domain": domain
            })
        return summary


# Funções para IAs
def get_ha_status():
    status = HomeAssistantAPI().check_connection()
    if status["status"] == "connected":
        return f"OK: {status['message']}"
    return f"ERRO: {status['message']}"


def list_devices(domain=None):
    ha = HomeAssistantAPI()
    devices = ha.get_devices_by_domain(domain) if domain else ha.get_states()
    lines = []
    for d in devices:
        lines.append(f"{ha.get_friendly_name(d)} ({d.get('entity_id')}): {d.get('state')}")
    return "\n".join(lines)


def control_device(entity_id, action, **params):
    ha = HomeAssistantAPI()
    domain = entity_id.split(".")[0]
    ha.call_service(domain, action, entity_id, **params)
    s = ha.get_state(entity_id)
    return f"{ha.get_friendly_name(s)}: {action} -> {s.get('state')}"


def configure_token(token):
    c = HAConfig.load()
    c.token = token
    c.save()
    return HomeAssistantAPI(token=token).check_connection()


if __name__ == "__main__":
    import sys
    print("Home Assistant API Client")
    print("=" * 40)
    print(get_ha_status())
    
    if len(sys.argv) > 2 and sys.argv[1] == "configure":
        print(configure_token(sys.argv[2]))
    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        print(list_devices(sys.argv[2] if len(sys.argv) > 2 else None))
