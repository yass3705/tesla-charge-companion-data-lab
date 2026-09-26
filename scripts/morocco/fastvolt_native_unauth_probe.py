#!/usr/bin/env python3
import json, ssl, socket, http.client, base64, os
from datetime import datetime, timezone

HOST="mobile.ev.fastvolt.ma"
REPORT="reports/morocco/fastvolt/latest-native-unauth-surface.json"

SAFE_HEADERS={"content-type","allow","www-authenticate","server","access-control-allow-origin","access-control-allow-methods"}

def http_probe(method,path,body=None):
    conn=http.client.HTTPSConnection(HOST, timeout=15, context=ssl.create_default_context())
    headers={"User-Agent":"TCC-FastVolt-ReadOnly-Probe/1.0","Accept":"application/json"}
    payload=None
    if body is not None:
        payload=json.dumps(body).encode()
        headers["Content-Type"]="application/json"
    try:
        conn.request(method,path,body=payload,headers=headers)
        r=conn.getresponse()
        data=r.read(2048)
        safe={k.lower():v for k,v in r.getheaders() if k.lower() in SAFE_HEADERS}
        return {"method":method,"path":path,"status":r.status,"reason":r.reason,
                "headers":safe,"sample_bytes":len(data),"body_persisted":False}
    except Exception as e:
        return {"method":method,"path":path,"error":type(e).__name__,"body_persisted":False}
    finally:
        try: conn.close()
        except Exception: pass

def websocket_handshake():
    key=base64.b64encode(os.urandom(16)).decode()
    req=(
        "GET / HTTP/1.1\r\n"
        f"Host: {HOST}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Origin: https://www.fastvolt.net\r\n"
        "User-Agent: TCC-FastVolt-ReadOnly-Probe/1.0\r\n\r\n"
    ).encode()
    raw=socket.create_connection((HOST,443),timeout=15)
    s=ssl.create_default_context().wrap_socket(raw,server_hostname=HOST)
    try:
        s.sendall(req)
        data=s.recv(4096).decode("iso-8859-1","replace")
        lines=data.split("\r\n")
        status_line=lines[0] if lines else ""
        safe_headers={}
        for line in lines[1:]:
            if ":" not in line: continue
            k,v=line.split(":",1)
            if k.lower() in {"upgrade","connection","server","www-authenticate","sec-websocket-protocol"}:
                safe_headers[k.lower()]=v.strip()
        return {"url":f"wss://{HOST}/","status_line":status_line,"headers":safe_headers,
                "payload_sent_after_handshake":False,"response_body_persisted":False}
    except Exception as e:
        return {"url":f"wss://{HOST}/","error":type(e).__name__,
                "payload_sent_after_handshake":False,"response_body_persisted":False}
    finally:
        try:s.close()
        except Exception:pass

probes=[]
for method,path,body in [
    ("OPTIONS","/auth/authorize",None),
    ("GET","/auth/authorize",None),
    ("POST","/auth/authorize",{}),
    ("OPTIONS","/app/charging_stations/",None),
    ("GET","/app/charging_stations/",None),
    ("OPTIONS","/user/get_charging_station_details/",None),
    ("GET","/user/get_charging_station_details/",None),
]:
    probes.append(http_probe(method,path,body))

ws=websocket_handshake()
statuses=[p.get("status") for p in probes if "status" in p]
report={
    "schema_version":1,
    "generated_at":datetime.now(timezone.utc).isoformat(),
    "country":"MA",
    "network":"FastVolt",
    "target":{"host":HOST,"client_version_context":"FastVolt Android 2.8.9"},
    "policy":{
        "read_only":True,
        "no_login":True,
        "no_credentials":True,
        "no_firebase_anonymous_account_creation":True,
        "no_otp":True,
        "no_charging_or_account_mutations":True,
        "response_bodies_not_persisted":True,
        "websocket_no_payload_after_handshake":True
    },
    "http_probes":probes,
    "websocket_probe":ws,
    "summary":{
        "http_statuses":statuses,
        "websocket_upgrade_without_auth":ws.get("status_line","").startswith("HTTP/1.1 101")
    }
}
os.makedirs(os.path.dirname(REPORT),exist_ok=True)
with open(REPORT,"w",encoding="utf-8") as f:
    json.dump(report,f,ensure_ascii=False,indent=2); f.write("\n")
print(json.dumps(report["summary"],indent=2))
