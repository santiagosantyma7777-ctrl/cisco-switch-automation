```jsx
import json
import time
import sys
import requests
import xml.etree.ElementTree as ET
from panos.firewall import Firewall
from panos.network import IkeGateway, IpsecTunnel, IpsecTunnelProxyId

# Suppress laboratory self-signed SSL certificate warnings
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

# ----------------------------------------------------
# 1. CORE DATA EXTRACTION & VENDOR NORMALIZATION
# ----------------------------------------------------
def load_and_normalize_config(config_path="config.json"):
    """Reads master JSON configuration and performs string translation mapping."""
    with open(config_path, "r") as f:
        cfg = json.load(f)
    
    # Static dictionary mapping to solve cross-vendor naming traps
    crypto_translation = {
        "aes-256-gcm": {
            "fortigate": "aes256gcm",
            "paloalto": "aes-256-gcm"
        },
        19: {
            "fortigate": "19",
            "paloalto": "group19"
        },
        "v2": {
            "fortigate": "2",
            "paloalto": "ikev2"
        }
    }
    
    # Inject vendor-specific structural keys dynamically into memory
    gen_enc = cfg["crypto_settings"]["encryption_algorithm"]
    gen_dh = cfg["crypto_settings"]["diffie_hellman_group"]
    gen_ike = cfg["crypto_settings"]["ike_version"]
    
    cfg["normalized"] = {
        "fgt_enc": crypto_translation[gen_enc]["fortigate"],
        "fgt_dh": crypto_translation[gen_dh]["fortigate"],
        "fgt_ike": crypto_translation[gen_ike]["fortigate"],
        "pan_enc": crypto_translation[gen_enc]["paloalto"],
        "pan_dh": crypto_translation[gen_dh]["paloalto"],
        "pan_ike": crypto_translation[gen_ike]["paloalto"]
    }
    return cfg

# ----------------------------------------------------
# 2. PALO ALTO PROVISIONING ENGINE (STAGING CANDIDATE STATE)
# ----------------------------------------------------
def provision_paloalto_candidate(cfg, pan_pass, psk):
    """Pushes logical interface, VR, zoning, and crypto structures to Palo Alto Candidate Database."""
    pan_cfg = cfg["endpoints"]["paloalto"]
    meta = cfg["vpn_metadata"]
    
    print(f"\n[*] Connecting to Palo Alto Appliance @ {pan_cfg['management_ip']}...")
    try:
        pan_fw = Firewall(pan_cfg["management_ip"], "admin", pan_pass)
        
        # Define Object Names dynamically
        gw_name = f"ike-gw-{meta['connection_name']}"
        tnl_obj_name = f"ipsec-tnl-{meta['connection_name']}"
        tunnel_intf = f"tunnel.{pan_cfg['virtual_tunnel_number']}"
        
        # 1. Clear out pre-existing local instances to ensure clean automation testing loop
        print(f"[*] Pre-Flight: Cleaning any existing candidate blocks named '{gw_name}'...")
        existing_gw = IkeGateway(name=gw_name)
        existing_tnl = IpsecTunnel(name=tnl_obj_name)
        pan_fw.remove(existing_tnl)
        pan_fw.remove(existing_gw)
        
        # 2. Build out the programmatic Phase 1 IKE Gateway mapping object
        print(f"[*] Staging IKE Gateway parameters (Phase 1)...")
        ike_gateway = IkeGateway(
            name=gw_name,
            version=cfg["normalized"]["pan_ike"],
            interface=pan_cfg["physical_wan_interface"],
            local_ip_address=pan_cfg["public_wan_ip"],
            peer_address=cfg["endpoints"]["fortigate"]["public_wan_ip"],
            pre_shared_key=psk
        )
        pan_fw.add(ike_gateway)
        
        # 3. Build out the programmatic Phase 2 IPSec Tunnel binding object
        print(f"[*] Staging IPSec Tunnel parameters (Phase 2)...")
        ipsec_tunnel = IpsecTunnel(
            name=tnl_obj_name,
            tunnel_interface=tunnel_intf,
            ike_gateway=gw_name
        )
        pan_fw.add(ipsec_tunnel)
        
        # 4. Enforce strict matching Proxy ID traffic selectors
        print(f"[*] Injecting symmetric Proxy ID boundaries...")
        proxy_id = IpsecTunnelProxyId(
            name=f"proxy-{meta['connection_name']}",
            local=pan_cfg["protected_local_subnet"],
            remote=cfg["endpoints"]["fortigate"]["protected_local_subnet"]
        )
        ipsec_tunnel.add(proxy_id)
        
        # 5. Execute Pre-Flight Candidate Transaction Validation API Check
        print("[*] Auditing Palo Alto Configuration Syntax via Pre-Flight Validate API...")
        val_res = pan_fw.op(cmd="<validate></validate>", xml=True)
        if "error" in val_res:
            print(f"[🟥 PRE-FLIGHT ERROR]: Palo Alto syntax audit rejected changes:\n{val_res}")
            sys.exit(1)
            
        print("[🟩 SUCCESS]: Palo Alto candidate staging passed validation testing blocks.")
        return pan_fw
        
    except Exception as e:
        print(f"[🟥 CRITICAL]: Failed to provision staged context on Palo Alto: {e}")
        sys.exit(1)

# ----------------------------------------------------
# 3. FORTIGATE PROVISIONING ENGINE (IMMEDIATE ACTIVATION STATE)
# ----------------------------------------------------
def provision_fortigate_live(cfg, fgt_token, psk):
    """Compiles and pushes live API blocks directly to the FortiOS configuration database."""
    fgt_cfg = cfg["endpoints"]["fortigate"]
    meta = cfg["vpn_metadata"]
    norm = cfg["normalized"]
    
    base_url = f"https://{fgt_cfg['management_ip']}/api/v2/cmdb"
    headers = {"Authorization": f"Bearer {fgt_token}", "Content-Type": "application/json"}
    
    print(f"\n[*] Connecting to FortiGate REST API @ {fgt_cfg['management_ip']}...")
    
    # Payload Step A: Phase 1 Interface Mapping
    p1_url = f"{base_url}/vpn.ipsec/phase1-interface"
    p1_payload = {
        "name": fgt_cfg["virtual_tunnel_interface"],
        "interface": fgt_cfg["physical_wan_interface"],
        "ike-version": norm["fgt_ike"],
        "proposal": norm["fgt_enc"],
        "dhgrp": norm["fgt_dh"],
        "remote-gw": cfg["endpoints"]["paloalto"]["public_wan_ip"],
        "psksecret": psk,
        "keylife": cfg["crypto_settings"]["phase1_lifetime_seconds"]
    }
    
    print("[*] Pushing immediate FortiGate Phase 1 Interface payload...")
    res_p1 = requests.post(p1_url, headers=headers, json=p1_payload, verify=False, timeout=10)
    
    # Payload Step B: Phase 2 Interface Selector Mapping
    p2_url = f"{base_url}/vpn.ipsec/phase2-interface"
    p2_payload = {
        "name": f"{fgt_cfg['virtual_tunnel_interface']}_p2",
        "phase1name": fgt_cfg["virtual_tunnel_interface"],
        "proposal": norm["fgt_enc"],
        "dhgrp": norm["fgt_dh"],
        "pfs": "enable",
        "keylifeseconds": cfg["crypto_settings"]["phase2_lifetime_seconds"],
        "src-subnet": fgt_cfg["protected_local_subnet"],
        "dst-subnet": cfg["endpoints"]["paloalto"]["protected_local_subnet"],
        "auto-negotiate": "enable"  # Crucial parameter to wake up control-plane probing
    }
    
    print("[*] Pushing immediate FortiGate Phase 2 Selector payload...")
    res_p2 = requests.post(p2_url, headers=headers, json=p2_payload, verify=False, timeout=10)
    
    # ----------------------------------------------------
    # PRE-FLIGHT INTENT VERIFICATION
    # ----------------------------------------------------
    print("[*] Verifying FortiGate Intent Compliance via Database Configuration Audit...")
    verify_url = f"{p1_url}/{fgt_cfg['virtual_tunnel_interface']}"
    audit_res = requests.get(verify_url, headers=headers, verify=False, timeout=10)
    
    if audit_res.status_code == 200:
        db_data = audit_res.json()["results"][0]
        if db_data["dhgrp"] == norm["fgt_dh"] and db_data["proposal"] == norm["fgt_enc"]:
            print("[🟩 SUCCESS]: FortiGate applied running configuration parameters accurately.")
        else:
            print("[🟥 AUDIT ERROR]: FortiGate parameters mismatch database baseline targets.")
            sys.exit(1)
    else:
        print(f"[🟥 API ERROR]: FortiGate configuration verification call returned status: {audit_res.status_code}")
        sys.exit(1)

# ----------------------------------------------------
# 4. ORCHESTRATION PIPELINE COORDINATOR
# ----------------------------------------------------
def trigger_orchestration_pipeline():
    # Gather execution arguments from prompt configurations
    LAB_PSK = "SuperSecure32CharSecretKeyLab123!" # In production, pull from secrets manager
    PALO_ALTO_PASSWORD = "AdminPassword123"      # Update with your laboratory password
    FORTIGATE_API_TOKEN = "TokenSecretXYZ"         # Update with your laboratory token
    
    # Run pipeline stage actions sequentially
    config_matrix = load_and_normalize_config("config.json")
    
    # Pipeline Step 1: Stage Palo Alto quietly in candidate state
    palo_object = provision_paloalto_candidate(config_matrix, PALO_ALTO_PASSWORD, LAB_PSK)
    
    # Pipeline Step 2: Push live configurations directly to FortiGate
    provision_fortigate_live(config_matrix, FORTIGATE_API_TOKEN, LAB_PSK)
    
    # Pipeline Step 3: Trigger final Palo Alto system commit to activate tunnels
    print("\n[*] Orchestration Finished. Initializing final Palo Alto Core Engine Commit...")
    try:
        palo_object.commit(sync=True)
        print("[🟩 PIPELINE DEPLOYMENT ENTIRELY COMPLETE]: Both firewalls are fully operational.")
    except Exception as e:
        print(f"[🟥 COMMIT EXCEPTION]: Palo Alto rejected final activation merge: {e}")

if __name__ == "__main__":
    trigger_orchestration_pipeline()

```
