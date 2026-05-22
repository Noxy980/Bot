from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import time
from collections import deque

app = Flask(__name__, static_folder='static')
CORS(app)

# ── Stockage multi-PC ─────────────────────────────────────────────────────────
# { pc_id: { "name": str, "last_seen": float, "queue": deque, "windows": list } }
pcs = {}

TIMEOUT = 8  # secondes sans ping → offline


def get_or_create_pc(pc_id, name=None):
    if pc_id not in pcs:
        pcs[pc_id] = {
            "name": name or pc_id,
            "last_seen": 0,
            "queue": deque(maxlen=50),
            "windows": []
        }
    elif name:
        pcs[pc_id]["name"] = name
    return pcs[pc_id]


# ── Page principale ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


# ── Routes appelées par le SITE WEB ──────────────────────────────────────────

@app.route('/api/pcs')
def list_pcs():
    """Retourne la liste de tous les PCs connus avec leur statut."""
    now = time.time()
    result = []
    for pc_id, pc in pcs.items():
        result.append({
            "id": pc_id,
            "name": pc["name"],
            "online": (now - pc["last_seen"]) < TIMEOUT
        })
    return jsonify(result)


@app.route('/api/status')
def status():
    """Le site vérifie si un PC spécifique est connecté."""
    pc_id = request.args.get('pc_id')
    if not pc_id or pc_id not in pcs:
        return jsonify({"online": False})
    online = (time.time() - pcs[pc_id]["last_seen"]) < TIMEOUT
    return jsonify({"online": online})


@app.route('/api/send', methods=['POST'])
def send_command():
    """Le site envoie une commande à un PC spécifique."""
    data = request.json
    if not data or 'type' not in data:
        return jsonify({"error": "Commande invalide"}), 400

    pc_id = data.get('pc_id')
    if not pc_id or pc_id not in pcs:
        return jsonify({"error": "PC introuvable"}), 404

    cmd = {
        "id": int(time.time() * 1000),
        "type": data["type"],
        "payload": data.get("payload", {}),
        "timestamp": time.time()
    }
    pcs[pc_id]["queue"].append(cmd)
    return jsonify({"ok": True, "id": cmd["id"]})


@app.route('/api/windows')
def get_windows():
    """Retourne la liste des fenêtres ouvertes sur un PC."""
    pc_id = request.args.get('pc_id')
    if not pc_id or pc_id not in pcs:
        return jsonify({"windows": []})
    return jsonify({"windows": pcs[pc_id]["windows"]})


# ── Routes appelées par le CLIENT PC ─────────────────────────────────────────

@app.route('/api/poll')
def poll():
    """Le client PC poll pour récupérer ses commandes en attente."""
    pc_id = request.args.get('pc_id')
    name = request.args.get('name', pc_id)

    if not pc_id:
        return jsonify({"commands": []})

    pc = get_or_create_pc(pc_id, name)
    pc["last_seen"] = time.time()

    commands = list(pc["queue"])
    pc["queue"].clear()
    return jsonify({"commands": commands})


@app.route('/api/report_windows', methods=['POST'])
def report_windows():
    """Le client PC envoie la liste de ses fenêtres ouvertes."""
    data = request.json
    if not data:
        return jsonify({"ok": False}), 400

    pc_id = data.get('pc_id')
    if not pc_id:
        return jsonify({"ok": False}), 400

    pc = get_or_create_pc(pc_id)
    pc["windows"] = data.get("windows", [])
    return jsonify({"ok": True})


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
