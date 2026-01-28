import requests
import base64
import re
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor

# Configuration
SOURCES = [
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",
    "https://raw.githubusercontent.com/IranianCypherpunks/sub/main/sub",
    "https://raw.githubusercontent.com/vfarid/v2ray-share/main/configs.txt",
    "https://raw.githubusercontent.com/iboxz/free-v2ray-collector/main/main/mix.txt"
]

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def check_ping(config):
    """Simple TCP ping check for basic availability"""
    try:
        # Extract host and port using regex
        host_port = re.search(r'@([^:/]+):(\d+)', config)
        if not host_port:
            return False
        
        host = host_port.group(1)
        port = int(host_port.group(2))
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            return True
    except:
        pass
    return False

def send_telegram_msg(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not found. Skipping notification.")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def collect():
    all_configs = []
    for source in SOURCES:
        try:
            print(f"Fetching from {source}...")
            response = requests.get(source, timeout=10)
            if response.status_code == 200:
                content = response.text
                # Handle base64 encoded sources
                if "://" not in content[:20]:
                    try:
                        content = base64.b64decode(content).decode('utf-8')
                    except:
                        pass
                
                configs = content.splitlines()
                all_configs.extend(configs)
        except Exception as e:
            print(f"Error fetching from {source}: {e}")

    # Remove duplicates and invalid lines
    unique_configs = list(set([c.strip() for c in all_configs if "://" in c]))
    print(f"Total unique configs found: {len(unique_configs)}")

    # Test configs in parallel
    print("Testing configs (TCP Ping)...")
    valid_configs = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(check_ping, unique_configs))
        for config, is_valid in zip(unique_configs, results):
            if is_valid:
                valid_configs.append(config)
    
    print(f"Total valid configs: {len(valid_configs)}")

    # Categorize
    categories = {
        "vless": [],
        "vmess": [],
        "trojan": [],
        "ss": [],
        "mix": valid_configs
    }

    for config in valid_configs:
        if config.startswith("vless://"): categories["vless"].append(config)
        elif config.startswith("vmess://"): categories["vmess"].append(config)
        elif config.startswith("trojan://"): categories["trojan"].append(config)
        elif config.startswith("ss://"): categories["ss"].append(config)

    # Save to files
    os.makedirs("configs", exist_ok=True)
    for cat, configs in categories.items():
        # Raw files
        with open(f"configs/{cat}.txt", "w") as f:
            f.write("\n".join(configs))
        
        # Base64 files for subscription
        with open(f"configs/{cat}_sub.txt", "w") as f:
            encoded = base64.b64encode("\n".join(configs).encode('utf-8')).decode('utf-8')
            f.write(encoded)

    # Send Telegram Notification
    msg = (
        "🔄 *V2Ray Collector Pro Updated!*\n\n"
        f"✅ Total Valid Configs: `{len(valid_configs)}` \n"
        f"🔹 VLESS: `{len(categories['vless'])}` \n"
        f"🔹 VMESS: `{len(categories['vmess'])}` \n"
        f"🔹 Trojan: `{len(categories['trojan'])}` \n"
        f"🔹 Shadowsocks: `{len(categories['ss'])}` \n\n"
        "🌐 [View on GitHub](https://github.com/MahanKenway/v2ray-collector-pro)"
    )
    send_telegram_msg(msg)

if __name__ == "__main__":
    collect()
