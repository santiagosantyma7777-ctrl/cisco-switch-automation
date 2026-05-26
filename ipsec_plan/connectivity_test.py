```jsx
import time
import json
import requests
import xml.etree.ElementTree as ET
from panos.firewall import Firewall

# Suppress laboratory self-signed SSL certificate warnings
requests.packages.urllib3.disable_warnings()

# Load configuration parameters from the schema file
with open("config.json") as f:
    cfg = json.load(f)

FGT_IP = cfg["endpoints"]["fortigate"]["mgmt_ip"]
FGT_TUNNEL_NAME = cfg["endpoints"]["fortigate"]["tunnel_interface_name"]
FGT_TOKEN = "YOUR_FORTIGATE_API_TOKEN" # Provide your real token here

PAN_IP = cfg["endpoints"]["paloalto"]["mgmt_ip"]
PAN_GW_NAME = f"ike-gw-{cfg['vpn_metadata']['connection_name']}"
PAN_TUNNEL_NAME = f"ipsec-tnl-{cfg['vpn_metadata']['connection_name']}"
PAN_USER = "admin"
PAN_PASS = "YOUR_PALO_ALTO_PASSWORD" # Provide your real password here

SOURCE_PING_IP = "10.0.1.1"       # Palo Alto local virtual or interface IP
TARGET_PING_IP = "192.168.80.1"   # FortiGate internal gateway IP

def get_palo_crypto_counters(pan_obj, tunnel_name):
    """Queries hardware ESP chip registers to fetch exact processing metrics."""
    try:
        cmd = f"<show><vpn><ipsec-sa><tunnel>{tunnel_name}</tunnel></ipsec-sa></vpn></show>"
        xml_res = pan_obj.op(cmd=cmd, xml=True)
        root = ET.fromstring(xml_res)
        entry = root.find(".//entry")
        if entry is not None:
            enc = int(entry.find(".//packets-encrypted").text or 0)
            dec = int(entry.find(".//packets-decrypted").text or 0)
            return {"encrypted": enc, "decrypted": dec}
    except Exception:
        pass
    return {"encrypted": 0, "decrypted": 0}

def run_lab_test_suite():
    print("[*] Connecting to Palo Alto via SDK...")
    pan_fw = Firewall(PAN_IP, PAN_USER, PAN_PASS)
    
    print("\n--- DIMENSION 1: RETRIEVING HARDWARE BASELINE COUNTERS ---")
    baseline = get_palo_crypto_counters(pan_fw, PAN_TUNNEL_NAME)
    print(f"[+] Baseline: Encrypted={baseline['encrypted']} | Decrypted={baseline['decrypted']}")
    
    print("\n--- DIMENSION 2: INJECTING TRAFFIC VIA PALO ALTO CORE ENGINE ---")
    ping_cmd = f"<ping><source>{SOURCE_PING_IP}</source><host>{TARGET_PING_IP}</host></ping>"
    ping_success = False
    try:
        ping_res = pan_fw.op(cmd=ping_cmd, xml=True)
        ping_text = "".join(ET.fromstring(ping_res).itertext())
        print(f"[*] Raw Ping Output Summary: {ping_text[:100]}...")
        if "alive" in ping_text or "bytes from" in ping_text:
            ping_success = True
    except Exception as e:
        print(f"[!] Traffic injection error: {e}")

    print("[*] Allowing 3 seconds for hardware register sync...")
    time.sleep(3)
    
    print("\n--- DIMENSION 3: RETRIEVING POST-TRAFFIC COUNTERS & DELTA ---")
    post = get_palo_crypto_counters(pan_fw, PAN_TUNNEL_NAME)
    enc_delta = post["encrypted"] - baseline["encrypted"]
    dec_delta = post["decrypted"] - baseline["decrypted"]
    print(f"[+] Post-Traffic: Encrypted={post['encrypted']} | Decrypted={post['decrypted']}")
    print(f"[+] Delta Calculated: Encrypted Delta=+{enc_delta} | Decrypted Delta=+{dec_delta}")

    print("\n==================================================")
    print("           FINAL LAB VERIFICATION REPORT          ")
    print("==================================================")
    if ping_success and dec_delta > 0:
        print("STATUS: 🟩 FLAWLESS SUCCESS (MODE 1)")
        print("ANALYSIS: Tunnel is active, routing is verified, and ICMP endpoints responded perfectly.")
    elif not ping_success and dec_delta > 0:
        print("STATUS: 🟩 CRYPTO SUCCESS / APPLICATION BLOCK (MODE 2)")
        print("ANALYSIS: The IPSec tunnel is functioning and encrypting/decrypting data properly.")
        print("          However, the remote FortiGate host dropped the ping reply.")
        print("          Action: Verify FortiGate interface allow-access rules or local OS firewall configs.")
    else:
        print("STATUS: 🟥 CRITICAL PIPELINE BREAKDOWN")
        print("ANALYSIS: Control plane failed to negotiate or security zones are misaligned.")
        print("          No hardware delta was recorded. Execute log diagnostics.")

if __name__ == "__main__":
    run_lab_test_suite()

```
