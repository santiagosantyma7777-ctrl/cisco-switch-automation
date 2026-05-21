import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import cisco_engine

# Load initial defaults from our secure local environment file
load_dotenv()

app = Flask(__name__)

@app.route('/')
def index():
    """Renders the main web interface panel populated with lab defaults."""
    context = {
        'default_host': os.getenv('DEFAULT_SWITCH_IP', ''),
        'default_user': os.getenv('DEFAULT_SWITCH_USER', ''),
        'default_pass': os.getenv('DEFAULT_SWITCH_PASSWORD', ''),
        'default_secret': os.getenv('DEFAULT_SWITCH_SECRET', '')
    }
    return render_template('index.html', **context)

def _extract_device_info(form_data):
    """Helper layout to pull connection details dynamically from frontend inputs."""
    return {
        'host': form_data.get('host'),
        'username': form_data.get('username'),
        'password': form_data.get('password'),
        'secret': form_data.get('secret')
    }

@app.route('/deploy', methods=['POST'])
def deploy():
    """Handles the blue granular config deployment trigger mechanism."""
    data = request.json
    device_info = _extract_device_info(data)
    hostname = data.get('hostname', 'SWITCH_AUTOMATED')
    
    # Map the exact mandatory target profile VLANs from the assignment instructions
    intended_vlans = [
        {'id': 10, 'name': data.get('vlan10_name', 'VLAN_DATA')},
        {'id': 20, 'name': data.get('vlan20_name', 'VLAN_VOICE')},
        {'id': 50, 'name': data.get('vlan50_name', 'VLAN_SECURITY')}
    ]
    
    result = cisco_engine.deploy_config(device_info, hostname, intended_vlans)
    logs = cisco_engine.get_log_output()
    return jsonify({'result': result, 'logs': logs})

@app.route('/validate', methods=['POST'])
def validate():
    """Handles the yellow operational validation loop state check."""
    data = request.json
    device_info = _extract_device_info(data)
    hostname = data.get('hostname', 'SWITCH_AUTOMATED')
    
    intended_vlans = [
        {'id': 10, 'name': data.get('vlan10_name', 'VLAN_DATA')},
        {'id': 20, 'name': data.get('vlan20_name', 'VLAN_VOICE')},
        {'id': 50, 'name': data.get('vlan50_name', 'VLAN_SECURITY')}
    ]
    
    result = cisco_engine.validate_config(device_info, hostname, intended_vlans)
    logs = cisco_engine.get_log_output()
    return jsonify({'result': result, 'logs': logs})

@app.route('/save', methods=['POST'])
def save():
    """Handles the green trigger targeting permanent NVRAM memory write routines."""
    data = request.json
    device_info = _extract_device_info(data)
    
    result = cisco_engine.save_config(device_info)
    logs = cisco_engine.get_log_output()
    return jsonify({'result': result, 'logs': logs})

@app.route('/backup', methods=['POST'])
def backup():
    """Handles the purple offbox raw configuration text dump routing."""
    data = request.json
    device_info = _extract_device_info(data)
    
    result = cisco_engine.backup_config(device_info)
    logs = cisco_engine.get_log_output()
    return jsonify({'result': result, 'logs': logs})

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    # Run server locally on loopback interface
    app.run(host='127.0.0.1', port=port, debug=True)

