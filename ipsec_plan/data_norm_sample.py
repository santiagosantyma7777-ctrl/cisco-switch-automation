import json

# 1. This is your single source of truth variable file
shared_vpn_config = {
    "connection_name": "hq-to-branch",
    "ike_version": "v2",
    "encryption": "aes-256-gcm",
    "dh_group": 19,
    "lifetime_p1": 86400,
    "lifetime_p2": 3600
}

# 2. Cryptographic Translation Dictionary
crypto_mapping = {
    "aes-256-gcm": {
        "fortigate": "aes256gcm",
        "paloalto": "aes-256-gcm"
    },
    19: {
        "fortigate": "19",         # FortiOS expects a string representation of the integer
        "paloalto": "group19"      # PAN-OS expects the 'group' prefix
    },
    "v2": {
        "fortigate": "2",
        "paloalto": "ikev2"
    }
}

def generate_vendor_payloads(config):
    # Extract generic variables
    gen_enc = config["encryption"]
    gen_dh = config["dh_group"]
    gen_ike = config["ike_version"]
    
    # 3. Translate into FortiGate API Payload format (JSON REST API)
    fortigate_payload = {
        "name": config["connection_name"],
        "ike-version": crypto_mapping[gen_ike]["fortigate"],
        "proposal": f"{crypto_mapping[gen_enc]['fortigate']}",
        "dhgrp": crypto_mapping[gen_dh]["fortigate"],
        "proposal-keepalive": "enable",
        "keylife": str(config["lifetime_p1"])  # Must be stringified
    }
    
    # 4. Translate into Palo Alto Object Payload format (pan-os-python SDK structure)
    paloalto_payload = {
        "name": config["connection_name"],
        "version": crypto_mapping[gen_ike]["paloalto"],
        "encryption": [crypto_mapping[gen_enc]['paloalto']], # PAN-OS expects a list
        "dh_group": [crypto_mapping[gen_dh]['paloalto']],    # PAN-OS expects a list
        "lifetime_seconds": config["lifetime_p1"]            # Keeps integer data type
    }
    
    return fortigate_payload, paloalto_payload

# Run the translation
fgt_data, pan_data = generate_vendor_payloads(shared_vpn_config)
print("--- FortiGate Payload ---")
print(json.dumps(fgt_data, indent=2))
print("\n--- Palo Alto Payload ---")
print(json.dumps(pan_data, indent=2))
