from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import time
from collections import deque

app = Flask(__name__, static_folder='static')
CORS(app)

# File d'attente des commandes par PC (max 50)
command_queues = {}   # pc_id -> deque
# Status des clients PC
pc_statuses = {}      # pc_id -> {online, last_seen, name}
# Fenêtres ouvertes par PC
pc_windows = {}       # pc_id -> list of {id, title}


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


# ── Routes appelées par le SITE WEB ──────────────────────────────────────────

@app.route('/api/pcs')
def list_pcs():
    """Liste les PCs connectés."""
    now = time.time()
    pcs = []
    for pc_id, status in pc_statuses.items():
        online = (now - status["last_seen"]) < 8
        pcs.append({
            "id": pc_id,
            "name": status.get("name", pc_id),
            "online": online
        })
    return jsonify({"pcs": pcs})


@app.route('/api/send', methods=['POST'])
def send_command():
    """Le site envoie une commande ici."""
    data = request.json
    if not data or 'type' not in data:
        return jsonify({"error": "Commande invalide"}), 400

    pc_id = data.get("pc_id", "default")
    if pc_id not in command_queues:
        command_queues[pc_id] = deque(maxlen=50)

    cmd = {
        "id": int(time.time() * 1000),
        "type": data["type"],
        "payload": data.get("payload", {}),
        "timestamp": time.time()
    }
    command_queues[pc_id].append(cmd)
    return jsonify({"ok": True, "id": cmd["id"]})


@app.route('/api/status')
def status():
    """Le site vérifie si un PC est connecté."""
    pc_id = request.args.get("pc_id", "default")
    if pc_id not in pc_statuses:
        return jsonify({"online": False})
    online = (time.time() - pc_statuses[pc_id]["last_seen"]) < 8
    return jsonify({"online": online, "name": pc_statuses[pc_id].get("name", pc_id)})


@app.route('/api/windows')
def get_windows():
    """Retourne la liste des fenêtres ouvertes sur un PC."""
    pc_id = request.args.get("pc_id", "default")
    return jsonify({"windows": pc_windows.get(pc_id, [])})


# ── Routes appelées par le CLIENT PC ─────────────────────────────────────────

@app.route('/api/poll')
def poll():
    """Le client PC long-poll pour récupérer les commandes en attente."""
    pc_id = request.args.get("pc_id", "default")
    pc_name = request.args.get("name", pc_id)

    if pc_id not in pc_statuses:
        pc_statuses[pc_id] = {}
    pc_statuses[pc_id]["online"] = True
    pc_statuses[pc_id]["last_seen"] = time.time()
    pc_statuses[pc_id]["name"] = pc_name

    if pc_id not in command_queues:
        command_queues[pc_id] = deque(maxlen=50)

    commands = list(command_queues[pc_id])
    command_queues[pc_id].clear()
    return jsonify({"commands": commands})


@app.route('/api/report_windows', methods=['POST'])
def report_windows():
    """Le client PC envoie la liste des fenêtres ouvertes."""
    data = request.json
    pc_id = data.get("pc_id", "default")
    pc_windows[pc_id] = data.get("windows", [])
    return jsonify({"ok": True})


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
