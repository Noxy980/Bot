from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import time
from collections import deque

app = Flask(__name__, static_folder='static')
CORS(app)

# Un dictionnaire par PC : { pc_id: { queue, last_seen, name } }
pcs = {}

def get_pc(pc_id):
    if pc_id not in pcs:
        pcs[pc_id] = {"queue": deque(maxlen=50), "last_seen": 0, "name": pc_id}
    return pcs[pc_id]


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


# ── Appelé par le SITE ───────────────────────────────────────────────────────

@app.route('/api/send', methods=['POST'])
def send_command():
    data = request.json
    if not data or 'type' not in data or 'pc_id' not in data:
        return jsonify({"error": "Données invalides"}), 400
    pc = get_pc(data['pc_id'])
    cmd = {
        "id": int(time.time() * 1000),
        "type": data["type"],
        "payload": data.get("payload", {}),
        "timestamp": time.time()
    }
    pc["queue"].append(cmd)
    return jsonify({"ok": True, "id": cmd["id"]})


@app.route('/api/pcs')
def list_pcs():
    """Retourne la liste des PCs connus avec leur statut."""
    now = time.time()
    result = []
    for pc_id, info in pcs.items():
        result.append({
            "id": pc_id,
            "name": info["name"],
            "online": (now - info["last_seen"]) < 8
        })
    return jsonify({"pcs": result})


# ── Appelé par le CLIENT PC ──────────────────────────────────────────────────

@app.route('/api/poll')
def poll():
    pc_id = request.args.get('pc_id')
    pc_name = request.args.get('name', pc_id)
    if not pc_id:
        return jsonify({"error": "pc_id manquant"}), 400
    pc = get_pc(pc_id)
    pc["last_seen"] = time.time()
    pc["name"] = pc_name
    commands = list(pc["queue"])
    pc["queue"].clear()
    return jsonify({"commands": commands})


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
