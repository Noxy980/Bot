from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import time
from collections import deque

app = Flask(__name__, static_folder='static')
CORS(app)

# File d'attente des commandes (max 50)
command_queue = deque(maxlen=50)
# Status du client PC
pc_status = {"online": False, "last_seen": 0}


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


# ── Routes appelées par le SITE WEB ──────────────────────────────────────────

@app.route('/api/send', methods=['POST'])
def send_command():
    """Le site envoie une commande ici."""
    data = request.json
    if not data or 'type' not in data:
        return jsonify({"error": "Commande invalide"}), 400

    cmd = {
        "id": int(time.time() * 1000),
        "type": data["type"],
        "payload": data.get("payload", {}),
        "timestamp": time.time()
    }
    command_queue.append(cmd)
    return jsonify({"ok": True, "id": cmd["id"]})


@app.route('/api/status')
def status():
    """Le site vérifie si le PC est connecté."""
    online = (time.time() - pc_status["last_seen"]) < 8
    return jsonify({"online": online})


# ── Routes appelées par le CLIENT PC ─────────────────────────────────────────

@app.route('/api/poll')
def poll():
    """Le client PC long-poll pour récupérer les commandes en attente."""
    pc_status["online"] = True
    pc_status["last_seen"] = time.time()

    commands = list(command_queue)
    command_queue.clear()
    return jsonify({"commands": commands})


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
