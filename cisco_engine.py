import io
import re
import logging
import socket
from datetime import datetime
from netmiko import ConnectHandler

# Explicitly catch all variations of connection and authentication failures
NetmikoExceptions = (Exception, socket.error, ConnectionRefusedError)


# Configure modular logging to capture and stream execution logs to the web UI
log_stream = io.StringIO()
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(log_stream),
        logging.StreamHandler()  # Keeps logs visible in the Linux terminal too
    ]
)
logger = logging.getLogger("CiscoEngine")

def get_log_output():
    """Returns the logged text accumulated in memory and clears the buffer."""
    logs = log_stream.getvalue()
    # Clear the buffer stream so logs don't accumulate endlessly across clicks
    log_stream.seek(0)
    log_stream.truncate(0)
    return logs

def _get_connection_dict(device_info):
    """Helper function to transform frontend connection fields to a Netmiko dict."""
    return {
        'device_type': 'cisco_ios',
        'host': device_info['host'],
        'username': device_info['username'],
        'password': device_info['password'],
        'secret': device_info['secret'],
        'fast_cli': False,
        # Netmiko native parameter to explicitly force backend paramiko to permit legacy RSA/SHA1 keys
        'disabled_algorithms': None
    }

def deploy_config(device_info, hostname, vlans_list):
    """Connects to the Cisco switch to modify the hostname and provision VLANs."""
    logger.info(f"Initiating SSH deployment connection to {device_info['host']}...")
    try:
        device = _get_connection_dict(device_info)
        with ConnectHandler(**device) as net_connect:
            net_connect.enable()
            logger.info("Authentication successful. Entering configuration mode.")
            
            config_commands = []
            
            # 1. Build Hostname changes
            if hostname:
                config_commands.append(f"hostname {hostname}")
                logger.info(f"Staging hostname change to: {hostname}")
                
            # 2. Build VLAN provisions
            for vlan in vlans_list:
                v_id = vlan.get('id')
                v_name = vlan.get('name')
                if v_id and v_name:
                    config_commands.extend([f"vlan {v_id}", f" name {v_name}"])
                    logger.info(f"Staging VLAN {v_id} with name: {v_name}")
            
            # Send configuration block to switch
            if config_commands:
                output = net_connect.send_config_set(config_commands)
                logger.info("Configuration commands successfully transmitted to device.")
                return {"status": "success", "message": "Configuration deployed successfully."}
            else:
                return {"status": "warning", "message": "No valid configurations were provided."}
                
    except NetmikoExceptions as e:
        logger.error(f"Network deployment operation failed: {str(e)}")
        return {"status": "error", "message": f"Deployment failed: {str(e)}"}

def validate_config(device_info, expected_hostname, expected_vlans):
    """Scrapes switch operational state using regex to validate against intent."""
    logger.info(f"Connecting to {device_info['host']} for operational state validation...")
    discrepancies = []
    
    try:
        device = _get_connection_dict(device_info)
        with ConnectHandler(**device) as net_connect:
            net_connect.enable()
            
            # 1. Hostname Validation Check
            logger.info("Validating device hostname state...")
            host_output = net_connect.send_command("show running-config | include hostname")
            match_host = re.search(r'^hostname\s+(\S+)', host_output, re.M)
            actual_hostname = match_host.group(1) if match_host else "Unknown"
            
            if actual_hostname != expected_hostname:
                discrepancies.append(f"Hostname Mismatch: Expected '{expected_hostname}', but device shows '{actual_hostname}'.")
                
            # 2. VLAN Table Validation Check
            logger.info("Validating operational VLAN database...")
            vlan_output = net_connect.send_command("show vlan brief")
            
            # Parse all active VLAN numbers and names into a local dictionary mapping
            active_vlans = {}
            for line in vlan_output.splitlines():
                match_vlan = re.search(r'^(\d+)\s+(\S+)', line.strip())
                if match_vlan:
                    active_vlans[match_vlan.group(1)] = match_vlan.group(2)
            
            # Cross-reference intended settings against scraped active states
            for ev in expected_vlans:
                target_id = str(ev['id'])
                target_name = ev['name']
                
                if target_id not in active_vlans:
                    discrepancies.append(f"Missing Profile: Intended VLAN {target_id} does not exist on the switch.")
                elif active_vlans[target_id] != target_name:
                    discrepancies.append(f"Name Mismatch on VLAN {target_id}: Expected '{target_name}', found operational name '{active_vlans[target_id]}'.")
            
            if discrepancies:
                for issue in discrepancies:
                    logger.warning(f"[DISCREPANCY DETECTED] {issue}")
                return {"status": "alert", "message": "Validation complete: Non-standard profile configuration patterns identified.", "errors": discrepancies}
            
            logger.info("State validation passed perfectly! Running profile fully matches intended state.")
            return {"status": "success", "message": "All settings validated successfully. 0 discrepancies found."}
            
    except NetmikoExceptions as e:
        logger.error(f"Validation collection loop encountered an issue: {str(e)}")
        return {"status": "error", "message": f"Validation process failed: {str(e)}"}

def save_config(device_info):
    """Performs write operations to commit dynamic memory setups into permanent NVRAM."""
    logger.info(f"Connecting to {device_info['host']} to save current running configuration...")
    try:
        device = _get_connection_dict(device_info)
        with ConnectHandler(**device) as net_connect:
            net_connect.enable()
            # Netmiko native utility abstraction to handle 'write memory' or 'copy run start' prompts
            output = net_connect.save_config()
            logger.info("Running-configuration successfully written to NVRAM startup-config.")
            return {"status": "success", "message": "Running configuration saved to NVRAM storage device memory."}
    except NetmikoExceptions as e:
        logger.error(f"NVRAM save transaction crashed: {str(e)}")
        return {"status": "error", "message": f"Save operation failed: {str(e)}"}

def backup_config(device_info):
    """Downloads a raw context plain-text dump of running-config to a local timestamped file."""
    logger.info(f"Retrieving active flat configuration from switch {device_info['host']} for offbox storage...")
    try:
        device = _get_connection_dict(device_info)
        with ConnectHandler(**device) as net_connect:
            net_connect.enable()
            
            # Grab hostname to build file dynamically
            host_output = net_connect.send_command("show running-config | include hostname")
            match_host = re.search(r'^hostname\s+(\S+)', host_output, re.M)
            hostname = match_host.group(1) if match_host else "SWITCH_UNKNOWN"
            
            # Fetch entire running config text
            running_config = net_connect.send_command("show running-config")
            
            # Formulate timestamped backup file path context targeting local backups/ path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backups/{hostname}_{timestamp}.cfg"
            
            with open(filename, "w") as backup_file:
                backup_file.write(running_config)
                
            logger.info(f"Backup file successfully generated locally: {filename}")
            return {"status": "success", "message": f"Configuration backup completed successfully: {filename}"}
            
    except NetmikoExceptions as e:
        logger.error(f"Offbox backup engine transaction terminated unexpectedly: {str(e)}")
        return {"status": "error", "message": f"Backup script generation sequence failed: {str(e)}"}

