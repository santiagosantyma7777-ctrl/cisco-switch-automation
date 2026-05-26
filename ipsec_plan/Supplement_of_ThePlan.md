# **Identification of Tools/APIs**

## **Native APIs and Device Interfaces**

<aside>
💡

- **FortiGate REST API**: Direct HTTP endpoints to configure VPN gateways (`vpn.ipsec/gateway`) and tunnels (`vpn.ipsec/phase1-interface`).
- **Palo Alto PAN-OS REST API**: Modern HTTP API to manage network interfaces, IKE crypto profiles, and IPSec tunnels.
- **Palo Alto XML API**: Legacy but highly comprehensive API using XPath expressions to manipulate the device configuration hierarchy.
- **FortiGate CLI / SSH**: Text-based configuration via industry-standard SSH connections.
- **Palo Alto CLI / SSH**: Structured command-line interface accessible via standard SSH sessions.
</aside>

## Infrastructure as Code (IaC) & Configuration Management

<aside>
💡

- **Terraform**: Uses official providers (`fortios` and `panos`) to declaratively build and maintain the VPN topology.
- **Ansible**: Utilizes targeted module collections (`fortinet.fortios` and `paloaltonetworks.panos`) for task-based configuration playbooks.
- **Python Libraries**: Uses `paramiko` or `netmiko` for raw SSH scripting, `pan-os-python` for Palo Alto API abstractions, and `requests` for direct HTTP calls
</aside>

If using Python: 

- Fortinet

<aside>
💡

- **`fortiosapi` (Official)**: This is Fortinet's official Python SDK. It interacts directly with the FortiGate REST API, allowing you to send JSON payloads to configure Phase 1, Phase 2, and firewall policies.
- **`pyFGT`**: A popular, lightweight open-source library specifically built for interacting with the FortiOS REST API
- **Napalm / Paramiko**: If you prefer SSH-based CLI automation rather than APIs, you can use `paramiko` or the `napalm-fortios` community driver to push standard CLI configuration scripts.
</aside>

- Palo Alto

<aside>
💡

- **`pan-os-python` (Official)**: This is their primary, officially maintained Python SDK. It provides an object-oriented abstraction layer over the Palo Alto XML API. Instead of writing raw XML, you write Python code like `gateway = network.IkeGateway(...)` and call `.apply()`.
- **`pan-python`**: A lower-level official utility library that provides the core wrapper for making raw XML API requests to PAN-OS or Panorama.
</aside>

## Centralized Management Platforms

<aside>
💡

- **FortiManager**: Fortinet's central management tool, which features its own JSON-RPC API to push VPN settings to FortiGate devices.
- **Palo Alto Panorama**: Centralized management platform featuring an XML/REST API to push template configurations to Palo Alto devices
</aside>

Third-party, vendor-agnostic network automation platforms

<aside>
💡

Vendor-Agnostic Orchestration Platforms

- **Anuta ATOM**: A multi-vendor network orchestration engine that automates the entire lifecycle of VPN provisioning across different firewall brands using model-driven workflows.
- **Itential**: A low-code network automation platform that integrates directly with Palo Alto and Fortinet APIs to build end-to-end VPN deployment workflows.
- **Gluware**: An enterprise-grade configuration management platform that uses intent-based networking to discover, validate, and push standardized VPN policies across disparate firewall vendors.
</aside>

<aside>
💡

Public Cloud Orchestrators (Hybrid Cloud)

- **AWS Transit Gateway Connect / Network Manager**: Automatically orchestrates and monitors IPsec VPN connections from on-premises FortiGate and Palo Alto appliances into AWS VPCs.
- **Azure Virtual WAN**: A networking service that provides optimized and automated branch-to-branch connectivity, allowing centralized VPN orchestration for certified Fortinet and Palo Alto customer premises equipment (CPE).
- **Google Cloud Network Connectivity Center**: A centralized hub that simplifies hybrid connectivity by managing and automating VPN tunnels from third-party firewalls directly into Google Cloud.
</aside>

<aside>
💡

Open-Source Automation Frameworks

- **AWX / Ansible Automation Platform**: While not a traditional GUI management tool, it serves as a centralized dashboard to run, schedule, and audit cross-vendor VPN deployment playbooks.
- **Nautobot / NetBox (with Plugins)**: These Network Source of Truth (NSoT) tools can be combined with automation engines to centrally track IP addresses and automatically trigger VPN builds on both devices.
</aside>

# **Automation Steps**

## IKE Gateway and IPSec Tunnel Objects - Palo Alto end

<aside>
💡

Python 

```jsx
from panos.network import IkeGateway, IpsecTunnel

# 1. Programmatically define Phase 1 (IKE Gateway)
ike_gw = IkeGateway(
    name="fgt-ike-gateway",
    version="ikev2",
    interface="ethernet1/2",          # Your public WAN interface
    local_ip_address="2.2.2.2",       # Palo Alto Public IP
    peer_address="1.1.1.1",           # FortiGate Public IP
    pre_shared_key="SecretKey123!",
    ike_crypto_profile="Your-IKE-Profile"
)
pan_firewall.add(ike_gw) # Stage to candidate config

# 2. Programmatically define Phase 2 (IPSec Tunnel) and bind it to tunnel.1
ipsec_tnl = IpsecTunnel(
    name="fgt-ipsec-tunnel",
    tunnel_interface="tunnel.1",      # Binds to your virtual interface
    ike_gateway="fgt-ike-gateway",    # Links to the Phase 1 gateway above
    ipsec_crypto_profile="Your-IPSec-Profile"
)
pan_firewall.add(ipsec_tnl) # Stage to candidate config

```

</aside>

## Firewall and zones

FortiGate Infrastructure Requirements

<aside>
💡

- **Zone Creation**: It is a best practice to create a generic zone named `VPN-Zones` and member-bind your new VPN tunnel interface to it. This keeps policies clean if you scale to multiple tunnels.
- **Firewall Policies**: FortiOS requires separate unidirectional policy objects. You must create two rules:
1. **Outbound**: Source: `Internal_LAN` | Destination: `Remote_Palo_LAN` | Interface: `Internal -> VPN-Zones` | Action: `Accept`
2. **Inbound**: Source: `Remote_Palo_LAN` | Destination: `Internal_LAN` | Interface: `VPN-Zones -> Internal` | Action: `Accept`
</aside>

Palo Alto Infrastructure Requirements

<aside>
💡

- **Zone Creation**: You must assign the `tunnel.X` interface to a specific Security Zone (e.g., `VPN-Zone`).
- **Security Policies**: PAN-OS allows a single rule to match multiple zone directions, but splitting them ensures tight state tracking:
    1. **Outbound**: Source Zone: `Trust-Zone` | Destination Zone: `VPN-Zone` | Source IP: `Local_LAN` | Destination IP: `Remote_FGT_LAN` | Action: `Allow`
    2. **Inbound**: Source Zone: `VPN-Zone` | Destination Zone: `Trust-Zone` | Source IP: `Remote_FGT_LAN` | Destination IP: `Local_LAN` | Action: `Allow`
</aside>

# **Specific Considerations** — challenges and considerations in heterogenous environment

## Require 2 configuration scripts

You **cannot** write a single configuration script or command template that runs natively on both FortiOS and PAN-OS. They use completely different operating systems, command structures, and API formats. Fortinet uses a structured Linux-like CLI and a JSON-based REST API. Palo Alto uses a hierarchical XML-based API and a distinct Junos-like CLI format. However, you **can** achieve a single unified design using an automation abstraction layer

## Crypto vector

- Both the firewalls support multi DH groups

### FortiOS

- Officially recommends **DH Group 19 or 31** for general deployments
- Multi DH groups is supported for both phase 1 and phase 2, will attempt to match the strongest common group with the peer



### PAN-OS

- The by design feature — automatically aligns specific cryptographic hashes to the chosen DH group to prevent insecure configurations. For example, selecting **Group 19** inherently links to a **SHA-256** hash, whereas selecting **Group 20** links to **SHA-384**
- If you choose `aes-128-gcm` or `aes-256-gcm` for IKE Phase 1 encryption, you **must** set the Authentication algorithm to `non-auth`, and you must match them with **Group 19 or Group 20** respectively.
- On phase 1, multi DH groups are supported, Palo Alto will try to match through top-to-bottom
- On phase 2, it only allows to select one HD group.

## Proxy ID match

<aside>
💡

- **FortiGate is Interface-Centric**: When you configure a VPN on a FortiGate, it automatically creates a virtual **Route-Based** interface (e.g., `vpn_to_palo`). You treat it like a real wire. You assign it an IP address and write standard static or dynamic routes (BGP) pointing to it.
- **Palo Alto is Proxy-Id Centric (Policy-Based / Route-Based Hybrid)**: Palo Alto forces you to explicitly bind the VPN to a `tunnel.X` interface, but it *also* relies heavily on **Traffic Selectors (Proxy IDs)**
- **The Automation Trap**: If FortiGate sends traffic without explicit Phase 2 selectors matching Palo Alto's Proxy IDs exactly, the tunnel will fail, even if the routing tables on both sides are perfect. Your automation script must strictly enforce identical local/remote subnet definitions on both sides
</aside>

## Data normalization

Data normalization should be taken care of carefully, as different vendors may use different names and data types.

If your master variable file says `group14`, your Python script has to translate that string differently for each vendor:

<aside>
💡

**FortiGate API/CLI expects**: `14`

**Palo Alto API/SDK expects**: `group14`

</aside>

If your script says `aes-256-gcm`:

<aside>
💡

**FortiGate expects**: `aes256gcm`

**Palo Alto expects**: `aes-256-gcm`

</aside>

## **The "Implicit Defaults" Blindspot**

<aside>
💡

- **Palo Alto’s Strict Defaults**: Palo Alto builds empty default cryptographic profiles, but if you do not explicitly assign an exact lifetime (e.g., 3600 seconds), it will apply its internal default.
- **FortiGate's "Auto-Discovery" Defaults**: FortiGate has default features like `auto-negotiate` (keeps the tunnel alive constantly) and `keep-alive` enabled out of the box. Palo Alto usually relies on traffic to bring a tunnel up unless DPDo (Dead Peer Detection) triggers it
- **The Fix**: Never rely on a vendor's default configuration in an automation script. Your script must explicitly define **every single variable** (Lifetimes, DPD timers, Key-Exchange versions) so neither firewall is forced to guess.
</aside>

## The State Control Vector (Commit vs. Immediate)

From a systems engineering perspective, how the firewalls apply code changes is radically different:

<aside>
💡

- **FortiGate is "Immediate"**: The moment your Python script sends an API call or CLI command to a FortiGate, it is live. If Phase 1 is configured but Phase 2 isn't ready yet, it immediately starts trying to negotiate and throwing errors in the logs.
- **Palo Alto is "Transactional"**: Palo Alto uses a Candidate Configuration. Your Python script can build the entire IKE gateway, tunnel interface, and crypto profiles in memory. Nothing happens until you issue a separate **`commit`** command.
- **The Automation Strategy**: Your script should configure the FortiGate first (or Palo Alto up until the commit stage), then push both live simultaneously so they don't flood syslog servers with phase-mismatch errors while the script is still running.
</aside>

## Summary Checklist

To defeat these challenges, your script's architecture must handle:

<aside>
💡

1. **Data Normalization**: Translate a neutral variable (like `dh_group: 19`) into vendor strings (`19` vs `group19`).
2. **Explicit Property Declaration**: Hardcode lifetimes and timers on both sides; leave nothing to vendor defaults.
3. **Phase 2 Selector Symmetry**: Ensure FortiGate's Phase 2 source/destination objects exactly mirror Palo Alto's Proxy IDs.
</aside>
