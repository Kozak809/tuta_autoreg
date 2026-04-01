import os, json, time, base64, subprocess as sp
from urllib.parse import urlparse, parse_qs, unquote

def parse_link(url):
    try:
        if "#" in url: url = url.split("#")[0]
        p = urlparse(url)
        q = {k: v[0] for k, v in parse_qs(p.query).items()}
        
        # Базовый тип
        scheme = p.scheme.lower()
        if scheme == "ss":
            scheme = "shadowsocks"
            
        ob = {"type": scheme, "tag": "proxy", "server": p.hostname, "server_port": p.port}
        
        if scheme == "vless":
            ob.update({
                "uuid": p.username,
                "packet_encoding": q.get("packetEncoding", "xudp")
            })
            if q.get("flow"):
                ob["flow"] = q.get("flow")
            
            if q.get("security") == "reality":
                ob["tls"] = {
                    "enabled": True,
                    "server_name": q.get("sni", p.hostname),
                    "reality": {
                        "enabled": True,
                        "public_key": q.get("pbk", ""),
                        "short_id": q.get("sid", "")
                    },
                    "utls": {"enabled": True, "fingerprint": q.get("fp", "chrome")}
                }
            elif q.get("security") == "tls" or p.port == 443:
                ob["tls"] = {"enabled": True, "server_name": q.get("sni", p.hostname), "utls": {"enabled": True, "fingerprint": q.get("fp", "chrome")}}
            
            if q.get("type") == "ws":
                ob["transport"] = {"type": "ws", "path": unquote(q.get("path", "/")), "headers": {"Host": q.get("host", p.hostname)}}
                
        elif scheme == "trojan":
            ob["password"] = unquote(p.username or "")
            if q.get("security") == "tls" or p.port == 443:
                ob["tls"] = {"enabled": True, "server_name": q.get("sni", p.hostname), "utls": {"enabled": True, "fingerprint": q.get("fp", "chrome")}}
            if q.get("type") == "ws":
                ob["transport"] = {"type": "ws", "path": unquote(q.get("path", "/")), "headers": {"Host": q.get("host", p.hostname)}}
        
        elif scheme == "shadowsocks":
            if p.username:
                try:
                    decoded = base64.urlsafe_b64decode(p.username + "=" * (-len(p.username) % 4)).decode().split(":", 1)
                    ob.update({"method": decoded[0], "password": decoded[1]})
                except:
                    ob.update({"method": p.username, "password": unquote(p.password or "")})

        elif scheme == "vmess":
            try:
                encoded_data = url[8:]
                decoded_data = base64.b64decode(encoded_data + "=" * (-len(encoded_data) % 4)).decode()
                v_data = json.loads(decoded_data)
                ob = {"type": "vmess", "tag": "proxy", "server": v_data["add"], "server_port": int(v_data["port"]), "uuid": v_data["id"], "security": v_data.get("scy", "auto")}
                if v_data.get("tls") == "tls" or v_data.get("port") == 443:
                    ob["tls"] = {"enabled": True, "server_name": v_data.get("sni", v_data["add"]), "utls": {"enabled": True, "fingerprint": "chrome"}}
                if v_data.get("net") == "ws":
                    ob["transport"] = {"type": "ws", "path": v_data.get("path", "/"), "headers": {"Host": v_data.get("host", v_data["add"])}}
            except: pass

        return [ob]
    except Exception as e:
        print(f"[!] Ошибка парсинга: {e}")
        return []

class ProxyManager:
    def __init__(self, link, port):
        self.link = link
        self.port = port
        self.tmp_config = f"temp/t_{port}.json"
        self.process = None

    def start(self):
        outbounds = parse_link(self.link)
        if not outbounds: return False
        cfg = {
            "log": {"level": "error"},
            "dns": {"servers": [{"tag": "google", "address": "8.8.8.8"}], "rules": [{"query_type": ["A", "AAAA"], "server": "google"}]},
            "inbounds": [{"type": "mixed", "listen": "127.0.0.1", "listen_port": self.port, "sniff": True}],
            "outbounds": outbounds,
            "route": {"final": "proxy"}
        }
        with open(self.tmp_config, 'w') as f: json.dump(cfg, f)
        self.process = sp.Popen(["sing-box", "run", "-c", self.tmp_config], stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        time.sleep(5)
        return True

    def stop(self):
        if self.process: self.process.kill()
        if os.path.exists(self.tmp_config): os.remove(self.tmp_config)
