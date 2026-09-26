#!/usr/bin/env python3
import json, ssl, socket, http.client, base64, os, select, struct, time
from datetime import datetime, timezone

HOST="mobile.ev.fastvolt.ma"
REPORT="reports/morocco/fastvolt/latest-native-unauth-surface.json"
SAFE_HEADERS={"content-type","allow","www-authenticate","server","access-control-allow-origin","access-control-allow-methods"}

def http_probe(method,path,body=None):
    conn=http.client.HTTPSConnection(HOST,timeout=15,context=ssl.create_default_context())
    headers={"User-Agent":"TCC-FastVolt-ReadOnly-Probe/1.1","Accept":"application/json"}
    payload=None
    if body is not None:
        payload=json.dumps(body).encode()
        headers["Content-Type"]="application/json"
    try:
        conn.request(method,path,body=payload,headers=headers)
        r=conn.getresponse(); data=r.read(2048)
        safe={k.lower():v for k,v in r.getheaders() if k.lower() in SAFE_HEADERS}
        return {"method":method,"path":path,"status":r.status,"reason":r.reason,
                "headers":safe,"sample_bytes":len(data),"body_persisted":False}
    except Exception as e:
        return {"method":method,"path":path,"error":type(e).__name__,"body_persisted":False}
    finally:
        try: conn.close()
        except Exception: pass

def recv_exact(sock,n):
    out=b""
    while len(out)<n:
        chunk=sock.recv(n-len(out))
        if not chunk: raise EOFError()
        out+=chunk
    return out

def read_server_frame(sock):
    h=recv_exact(sock,2)
    b1,b2=h[0],h[1]
    opcode=b1&0x0f
    masked=bool(b2&0x80)
    length=b2&0x7f
    if length==126: length=struct.unpack("!H",recv_exact(sock,2))[0]
    elif length==127: length=struct.unpack("!Q",recv_exact(sock,8))[0]
    mask=recv_exact(sock,4) if masked else None
    payload=recv_exact(sock,length) if length else b""
    if mask:
        payload=bytes(v^mask[i%4] for i,v in enumerate(payload))
    item={"opcode":opcode,"payload_bytes":len(payload)}
    if opcode==1:
        txt=payload.decode("utf-8","replace")
        item["text_shape"]="text"
        candidate=txt
        if txt and txt[0].isdigit() and len(txt)>1 and txt[1] in "[{":
            item["socketio_prefix"]=txt[0]
            candidate=txt[1:]
        try:
            obj=json.loads(candidate)
            item["text_shape"]="json_object" if isinstance(obj,dict) else "json_array" if isinstance(obj,list) else "json_scalar"
            if isinstance(obj,dict):
                item["json_keys"]=sorted(str(k) for k in obj.keys())[:40]
            elif isinstance(obj,list):
                item["json_length"]=len(obj)
        except Exception:
            item["text_length"]=len(txt)
    return item

def build_client_text_frame(payload_text):
    payload=payload_text.encode("utf-8")
    first=0x81
    mask=os.urandom(4)
    n=len(payload)
    if n<126:
        header=bytes([first,0x80|n])
    elif n<65536:
        header=bytes([first,0x80|126])+struct.pack("!H",n)
    else:
        header=bytes([first,0x80|127])+struct.pack("!Q",n)
    masked=bytes(b ^ mask[i%4] for i,b in enumerate(payload))
    return header+mask+masked

def websocket_handshake_and_passive_frames():
    key=base64.b64encode(os.urandom(16)).decode()
    req=(
        "GET / HTTP/1.1\r\n"
        f"Host: {HOST}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Origin: https://www.fastvolt.net\r\n"
        "User-Agent: TCC-FastVolt-ReadOnly-Probe/1.1\r\n\r\n"
    ).encode()
    raw=socket.create_connection((HOST,443),timeout=15)
    s=ssl.create_default_context().wrap_socket(raw,server_hostname=HOST)
    try:
        s.sendall(req)
        buf=b""
        while b"\r\n\r\n" not in buf and len(buf)<16384:
            buf+=s.recv(4096)
        head,rest=(buf.split(b"\r\n\r\n",1)+[b""])[:2]
        lines=head.decode("iso-8859-1","replace").split("\r\n")
        status_line=lines[0] if lines else ""
        safe_headers={}
        for line in lines[1:]:
            if ":" not in line: continue
            k,v=line.split(":",1)
            if k.lower() in {"upgrade","connection","server","www-authenticate","sec-websocket-protocol"}:
                safe_headers[k.lower()]=v.strip()
        frames=[]
        if status_line.startswith("HTTP/1.1 101"):
            s.setblocking(False)
            deadline=time.monotonic()+4.0
            while time.monotonic()<deadline and len(frames)<5:
                ready,_,_=select.select([s],[],[],max(0,deadline-time.monotonic()))
                if not ready: break
                s.setblocking(True)
                s.settimeout(max(0.2,deadline-time.monotonic()))
                try:
                    frames.append(read_server_frame(s))
                except Exception as e:
                    frames.append({"read_error":type(e).__name__})
                    break
                finally:
                    s.setblocking(False)
        return {"url":f"wss://{HOST}/","status_line":status_line,"headers":safe_headers,
                "passive_frames":frames,"client_application_payload_sent":False,
                "response_payload_values_persisted":False}
    except Exception as e:
        return {"url":f"wss://{HOST}/","error":type(e).__name__,
                "client_application_payload_sent":False,"response_payload_values_persisted":False}
    finally:
        try:s.close()
        except Exception:pass

def websocket_synthetic_registration_probe():
    tenant_id="fa14e7c0-4aac-41d5-b373-fb2gh90241d"
    synthetic_user_id="tcc-readonly-probe-nonexistent"
    key=base64.b64encode(os.urandom(16)).decode()
    req=(
        "GET / HTTP/1.1\r\n"
        f"Host: {HOST}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Origin: https://www.fastvolt.net\r\n"
        "User-Agent: TCC-FastVolt-ReadOnly-Probe/1.2\r\n\r\n"
    ).encode()
    raw=socket.create_connection((HOST,443),timeout=15)
    sock=ssl.create_default_context().wrap_socket(raw,server_hostname=HOST)
    try:
        sock.sendall(req)
        buf=b""
        while b"\r\n\r\n" not in buf and len(buf)<16384:
            buf+=sock.recv(4096)
        head,rest=(buf.split(b"\r\n\r\n",1)+[b""])[:2]
        status_line=head.decode("iso-8859-1","replace").split("\r\n")[0]
        frames=[]
        if not status_line.startswith("HTTP/1.1 101"):
            return {"status_line":status_line,"registration_sent":False,"response_frames":[]}
        payload=json.dumps({"user_id":synthetic_user_id,"tenant_id":tenant_id},separators=(",",":"))
        sock.sendall(build_client_text_frame(payload))
        deadline=time.monotonic()+5.0
        while time.monotonic()<deadline and len(frames)<8:
            ready,_,_=select.select([sock],[],[],max(0,deadline-time.monotonic()))
            if not ready: break
            sock.settimeout(max(0.2,deadline-time.monotonic()))
            try:
                frame=read_server_frame(sock)
                # Preserve only structural metadata. For JSON, allow event name and key names.
                if frame.get("opcode")==1:
                    # read_server_frame deliberately does not persist payload values.
                    pass
                frames.append(frame)
            except Exception as e:
                frames.append({"read_error":type(e).__name__})
                break
        return {
            "status_line":status_line,
            "registration_sent":True,
            "registration_shape":{"keys":["tenant_id","user_id"],"user_id_kind":"synthetic_nonexistent","tenant_id_source":"FastVolt 2.8.9 static client"},
            "response_frames":frames,
            "response_payload_values_persisted":False
        }
    except Exception as e:
        return {"error":type(e).__name__,"registration_sent":False,"response_frames":[]}
    finally:
        try:sock.close()
        except Exception:pass

probes=[]
for method,path,body in [
    ("OPTIONS","/auth/authorize",None),("GET","/auth/authorize",None),("POST","/auth/authorize",{}),
    ("OPTIONS","/app/charging_stations/",None),("GET","/app/charging_stations/",None),
    ("OPTIONS","/user/get_charging_station_details/",None),("GET","/user/get_charging_station_details/",None),
]:
    probes.append(http_probe(method,path,body))

ws=websocket_handshake_and_passive_frames()
ws_synthetic=websocket_synthetic_registration_probe()
report={
    "schema_version":3,
    "generated_at":datetime.now(timezone.utc).isoformat(),
    "country":"MA","network":"FastVolt",
    "target":{"host":HOST,"client_version_context":"FastVolt Android 2.8.9"},
    "policy":{"read_only":True,"no_login":True,"no_credentials":True,
              "no_firebase_anonymous_account_creation":True,"no_otp":True,
              "no_charging_or_account_mutations":True,"response_bodies_not_persisted":True,
              "websocket_passive_probe":True,
              "synthetic_registration_only":True,
              "synthetic_user_id_is_deliberately_nonexistent":True,
              "no_real_user_identifier_sent":True},
    "http_probes":probes,
    "websocket_probe":ws,
    "websocket_synthetic_registration_probe":ws_synthetic,
    "summary":{"http_statuses":[p.get("status") for p in probes if "status" in p],
               "websocket_upgrade_without_auth":ws.get("status_line","").startswith("HTTP/1.1 101"),
               "passive_websocket_frame_count":len(ws.get("passive_frames",[])),
               "passive_websocket_text_shapes":[f.get("text_shape") for f in ws.get("passive_frames",[]) if f.get("text_shape")],
               "synthetic_registration_sent":ws_synthetic.get("registration_sent") is True,
               "synthetic_registration_response_frame_count":len(ws_synthetic.get("response_frames",[])),
               "synthetic_registration_response_shapes":[f.get("text_shape") for f in ws_synthetic.get("response_frames",[]) if f.get("text_shape")]}
}
os.makedirs(os.path.dirname(REPORT),exist_ok=True)
with open(REPORT,"w",encoding="utf-8") as f:
    json.dump(report,f,ensure_ascii=False,indent=2); f.write("\n")
print(json.dumps(report["summary"],indent=2))
