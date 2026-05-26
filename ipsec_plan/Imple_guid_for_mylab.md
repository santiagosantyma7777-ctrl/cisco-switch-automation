# IPSec VPN Automation Plan: FortiGate to Palo Alto Lab Blueprint

## Architectural Framework Strategy

### Decision on Management Tools (Cost vs. Feasibility)
For a lab environment, the deployment will utilize native REST/XML APIs (Direct Device Connections). 

Centralized management engines like FortiManager and Panorama require separate corporate licenses, significantly higher virtual machine compute allocations (RAM/CPU), and complex initial sync operations. Targeting direct device APIs allows for rapid, cost-free testing of the automation framework logic.

---

## Phase 1: Lab Topology & Architecture Blueprint

```text
[ Lab Internal Subnet ]                                                  [ Lab Internal Subnet ]
   192.168.80.0/24                                                           10.0.1.0/24


          |                                                                       |
          v                                                                       v
+-----------------------------+                                        +-----------------------------+

|    FORTIGATE FIREWALL       |                                        |     PALO ALTO FIREWALL      |
|  (Direct REST API Access)   |                                        |  (Direct XML API / SDK)     |
|                             |                                        |                             |
|  Physical WAN: wan1         | <========== Encrypted IPSec =========> |  Physical WAN: ethernet1/1  |
|  Public IP: 1.1.1.1         |             VPN Tunnel                 |  Public IP: 2.2.2.2         |
|                             |                                        |                             |
|  Tunnel Interface: vpn_palo |                                        |  Tunnel Interface: tunnel.1 |
|  Tunnel IP: 10.255.100.1/30 |                                        |  Tunnel IP: 10.255.100.2/30 |
+-----------------------------+                                        +-----------------------------+
```


### Cryptographic Standard Profile
* **IKE Protocol Version**: IKEv2
* **Phase 1 (IKE) Proposals**: AES-256-GCM | DH Group 19 | Lifetime: 86400 seconds
* **Phase 2 (IPSec) Proposals**: AES-256-GCM | DH Group 19 (PFS Enabled) | Lifetime: 3600 seconds
* **Tunnel Keep-Alive**: Enabled (`auto-negotiate` on FortiGate) to bring the tunnel up automatically without requiring client traffic.

---

## Phase 2: Master Variable Schema (`config.json`)
Save this unified, normalized dictionary file in your script directory. It serves as your single source of truth.

```json
{
  "vpn_metadata": {
    "connection_name": "lab-vpn-tunnel"
  },
  "crypto_settings": {
    "ike_version": "v2",
    "encryption": "aes-256-gcm",
    "dh_group": 19,
    "lifetime_p1_seconds": 86400,
    "lifetime_p2_seconds": 3600,
    "pfs_enabled": true
  },
  "network_transit": {
    "transit_cidr": "10.255.100.0/30"
  },
  "endpoints": {
    "fortigate": {
      "mgmt_ip": "192.168.1.99",
      "public_wan_ip": "1.1.1.1",
      "wan_interface_name": "wan1",
      "internal_lan_cidr": "192.168.80.0/24",
      "tunnel_interface_name": "vpn_palo"
    },
    "paloalto": {
      "mgmt_ip": "192.168.1.100",
      "public_wan_ip": "2.2.2.2",
      "wan_interface_name": "ethernet1/1",
      "internal_lan_cidr": "10.0.1.0/24",
      "tunnel_interface_number": 1,
      "security_zone_name": "VPN-Zone"
    }
  }
}
```

---

## Phase 3: Detailed Step-by-Step Implementation Sequence

### Step 1: Pre-requisites & Key Generation
1. Log into your Linux management machine or IDE terminal.
2. Generate a secure, high-entropy Pre-Shared Key (PSK) using Python's cryptographic library:
   ```bash
   python3 -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32)))"
   ```
3. Generate a dedicated API token on the FortiGate under **System > Administrators**.
4. Retrieve the API Key from the Palo Alto firewall via HTTPS request using your admin credentials.

### Step 2: Push Configurations to Palo Alto (Candidate State)
Your script must push these configuration changes to the Palo Alto first. Do **not** issue the commit command yet.
1. **Create Tunnel Interface**: Generate a logical Layer 3 interface named `tunnel.1`.
2. **Assign Zone**: Create a Security Zone called `VPN-Zone` (Layer 3 type) and make `tunnel.1` a member.
3. **Configure Routing**: Inside the `default` Virtual Router, add a static route pointing to the destination network `192.168.80.0/24` with an egress interface of `tunnel.1` and next-hop set to `None`. Add the `tunnel.1` interface to the VR interface list.
4. **Create Crypto Profiles**:
   * IKE Crypto Profile: AES-256-GCM | DH Group 19 | Lifetime 24 Hours.
   * IPSec Crypto Profile: AES-256-GCM | DH Group 19 | Lifetime 1 Hour.
5. **Create IKE Gateway**: Point to physical interface `ethernet1/1`, local IP `2.2.2.2`, peer address `1.1.1.1`, and input your generated PSK.
6. **Create IPSec Tunnel & Proxy ID**: Define an IPSec Tunnel object linking your IKE Gateway, IPSec Crypto Profile, and `tunnel.1`. Inside this object, create a Proxy ID: Local Subnet `10.0.1.0/24`, Remote Subnet `192.168.80.0/24`.
7. **Create Security Policies**: Create bidirectional stateful rules allowing traffic from your internal trust zone to `VPN-Zone`, and from `VPN-Zone` to your trust zone.

### Step 3: Push Configurations to FortiGate (Immediate Activation State)
Palo Alto is staged and quiet. Now, execute the FortiGate configurations. They will take effect immediately.
1. **Create Phase 1 Interface**: Target `/api/v2/cmdb/vpn.ipsec/phase1-interface/`. Bind to physical interface `wan1`, set remote gateway to `2.2.2.2`, input the matching PSK, set IKE version to `2`, proposal to `aes256gcm`, and DH group to `19`.
2. **Create Phase 2 Interface**: Target `/api/v2/cmdb/vpn.ipsec/phase2-interface/`. Link it to the Phase 1 interface, set encapsulation to ESP, proposal to `aes256gcm`, PFS to enable, DH group to `19`, source subnet to `192.168.80.0/24`, and destination subnet to `10.0.1.0/24`. Crucially, set `auto-negotiate` to `enable`.
3. **Assign Tunnel IP**: Assign `10.255.100.1/30` directly to the newly generated `vpn_palo` virtual interface.
4. **Configure Routing**: Create a static route pointing target subnet `10.0.1.0/24` down the `vpn_palo` interface.
5. **Create Firewall Policies**: Build two distinct firewall policy objects allowing traffic bidirectionally between your internal physical port and the `vpn_palo` virtual interface.

### Step 4: Finalise Palo Alto Commit
Execute a POST request to Palo Alto's API calling a configuration commit. The moment the commit success status reaches 100%, the Palo Alto engine comes alive, notices the active IKE probes hitting its WAN from the FortiGate, and begins negotiation.

## Phase 4: Two-Dimensional Lab Testing Script

This validation script performs an intentional data-plane ping test, checks the physical hardware cryptographic registers, calculates the byte change delta, and outputs a complete status report.

```python
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

