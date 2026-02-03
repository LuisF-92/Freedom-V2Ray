import requests
import base64
import json
import re
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor

# Configuration - Added more reliable sources
SOURCES = [
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/IranianCypherpunks/sub/main/sub",
    "https://raw.githubusercontent.com/vfarid/v2ray-share/main/configs.txt",
    "https://raw.githubusercontent.com/iboxz/free-v2ray-collector/main/main/mix.txt",
    "https://raw.githubusercontent.com/Lidatong/v2ray_rules/master/all.txt",
    "https://raw.githubusercontent.com/awesome-vpn/awesome-vpn/master/all.txt"
]

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def decode_base64(data):
    cleaned = data.strip()
    cleaned += "=" * (-len(cleaned) % 4)
    try:
        return base64.urlsafe_b64decode(cleaned).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None

def parse_vmess(config):
    payload = decode_base64(config[8:])
    if not payload:
        return None
    try:
        vmess_data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    host = vmess_data.get("add")
    port = vmess_data.get("port")
    if not host or not port:
        return None
    try:
        return host, int(port)
    except (TypeError, ValueError):
        return None

def parse_ss(config):
    data = config[5:]
    data = data.split("#", 1)[0]
    if "@" in data:
        host_port = data.split("@", 1)[1]
    else:
        decoded = decode_base64(data)
        if not decoded or "@" not in decoded:
            return None
        host_port = decoded.split("@", 1)[1]
    host_port = host_port.split("?", 1)[0]
    match = re.search(r"^([^:/]+):(\d+)$", host_port)
    if not match:
        return None
    return match.group(1), int(match.group(2))

def parse_host_port(config):
    if config.startswith("vmess://"):
        return parse_vmess(config)
    if config.startswith("ss://"):
        return parse_ss(config)
    match = re.search(r"@([^:/]+):(\d+)", config)
    if not match:
        return None
    return match.group(1), int(match.group(2))

def check_ping(config):
    """Improved TCP ping check with better parsing and timeout handling"""
    try:
        host_port = parse_host_port(config)
        if not host_port:
            return False
        host, port = host_port
        
        # DNS Resolution check
        try:
            ip = socket.gethostbyname(host)
        except socket.gaierror:
            return False

        # TCP Connect check
        start_time = time.perf_counter()
        try:
            with socket.create_connection((ip, port), timeout=1.5):
                end_time = time.perf_counter()
        except (socket.timeout, OSError):
            return False
        
        latency = int((end_time - start_time) * 1000)
        return latency < 1000 # Only keep configs with < 1s latency
    except Exception:
        pass
    return False

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def collect():
    all_configs = []
    for source in SOURCES:
        try:
            response = requests.get(source, timeout=15)
            if response.status_code == 200:
                content = response.text
                if "://" not in content[:50]:
                    decoded = decode_base64(content)
                    if decoded:
                        content = decoded
                all_configs.extend(content.splitlines())
        except requests.RequestException:
            pass

    unique_configs = list(set([c.strip() for c in all_configs if "://" in c]))
    
    # Parallel testing with more workers
    valid_configs = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(check_ping, unique_configs))
        for config, is_valid in zip(unique_configs, results):
            if is_valid: valid_configs.append(config)
    
    categories = {"vless": [], "vmess": [], "trojan": [], "ss": [], "mix": valid_configs}
    for config in valid_configs:
        if config.startswith("vless://"): categories["vless"].append(config)
        elif config.startswith("vmess://"): categories["vmess"].append(config)
        elif config.startswith("trojan://"): categories["trojan"].append(config)
        elif config.startswith("ss://"): categories["ss"].append(config)

    os.makedirs("configs", exist_ok=True)
    for cat, configs in categories.items():
        with open(f"configs/{cat}.txt", "w") as f: f.write("\n".join(configs))
        with open(f"configs/{cat}_sub.txt", "w") as f:
            f.write(base64.b64encode("\n".join(configs).encode('utf-8')).decode('utf-8'))

    msg = (
        "🚀 *Freedom V2Ray Updated!*\n\n"
        f"✅ High-Speed Configs: `{len(valid_configs)}` \n"
        f"🔹 VLESS: `{len(categories['vless'])}` \n"
        f"🔹 VMESS: `{len(categories['vmess'])}` \n"
        f"🔹 Trojan: `{len(categories['trojan'])}` \n"
        f"🔹 Shadowsocks: `{len(categories['ss'])}` \n\n"
        "⏱ Update Interval: `2 Hours` \n"
        "🌐 [View on GitHub](https://github.com/MahanKenway/Freedom-V2Ray)"
    )
    send_telegram_msg(msg)

if __name__ == "__main__":
    collect()
