# Cisco Infrastructure Automation & State Validation Console

A production-grade network automation framework built with Python, Flask, and Netmiko. This application implements a decoupled Frontend/Backend architecture designed to dynamically configure, validate, permanently commit, and back up configuration states on Cisco IOS devices.

## 🚀 Key Features & Architectural Highlights
- **Decoupled MVC Pattern:** Clean separation of presentation layers (Flask + Tailwind CSS UI) from core execution infrastructure (`cisco_engine.py`).
- **Granular Control Workflow:** Encourages safe network operations by breaking execution into discrete lifecycle phases (Deploy ➡️ Validate ➡️ Save ➡️ Backup).
- **Asynchronous Execution Log Streaming:** Intercepts low-level Netmiko runtime events and streams raw stdout buffers directly into a responsive, browser-based terminal view.
- **Regex State Parsing Engine:** Scrapes live device stdout via custom Regular Expression compilation blocks to validate current operational tables against desired configuration profiles without third-party abstraction dependencies.
- **Secure Secret Ingestion:** Utilizes local `.env` scoping boundaries to completely keep administrative authentication keys out of the source repository code.

---

## 🛠️ Prerequisites & Local Environment Setup

Ensure you have Python 3.10+ and standard network reachability to your target GNS3 or physical network appliances.

### 1. Initialize the Environment and Virtual Environment
Navigate to your clone root folder directory path and run:
```bash
# Create an isolated python environment shell
python3 -m venv venv

# Activate the local virtual tracking environment
source venv/bin/activate
```

### 2. Dependency Installation
Install the exact framework dependencies required by the script engine via the frozen requirements tracking table:
```bash
pip install -r requirements.txt
```

### 3. Environment Variable Configuration
Create a local file named `.env` in the root folder directory to supply structural defaults for your lab topology. This file is explicitly blocked from Git tracking via `.gitignore` policies.
```text
FLASK_PORT='your_flask_port'
DEFAULT_SWITCH_IP='your_default_switch_ip'
DEFAULT_SWITCH_USER='your_default_username'
DEFAULT_SWITCH_PASSWORD='your_default_password'
DEFAULT_SWITCH_SECRET='your_defautl_password'
```

---

## 💻 Running the Automation Dashboard

Start the local Python execution server from your active terminal session:
```bash
python app.py
```
Upon startup, fire up any standard web browser application tool and navigate directly to:
👉 **`http://127.0.0.1:5000`**

---

## 🕹️ Operations Interaction Guide

To safely execute network provisioning state lifecycles, perform your operations sequentially through the four color-coded buttons:

1. 🔵 **Deploy Configuration:** Transmits hostname intent changes and provisions the mandatory organizational network VLAN profile database tables (VLAN 10, VLAN 20, VLAN 50).
2. 🟡 **Validate Setup:** Scrapes operational `show vlan brief` and configuration buffers using regular expressions. If any parameter does not match your desired layout, it flashes descriptive alert strings in the dark log terminal window.
3. 🟢 **Save to NVRAM:** Programmatically executes permanent memory write instructions (`write memory`) to guarantee data survives device reboots.
4. 🟣 **Download Backup:** Performs a flat flat configuration dump and writes a timestamped `.cfg` file locally inside the `backups/` directory (e.g., `backups/SWITCH_AUTOMATED_20260522_234000.cfg`).

---

## 📂 Project Repository Tree File Layout

```text
cisco-switch-automation/
├── app.py                # Flask Server Controller and Web Routing Engine
├── cisco_engine.py       # Core Netmiko Execution & Parsing Driver
├── requirements.txt      # Frozen Third-Party Package Dependencies
├── .gitignore            # Git Tracking Exclusion Directory Boundaries
├── .env                  # Secure Authentication Keys (Kept Local)
├── README.md             # Project Architectural Documentation
├── backups/              # Offbox Storage Directory for Flat Configuration Backups
└── templates/
    └── index.html        # Dynamic Dark-Themed Async Dashboard Interface
```

