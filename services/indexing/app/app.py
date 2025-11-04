from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "indexing"}), 200

@app.route('/index', methods=['POST'])
def index():
    # Placeholder for indexing logic
    data = request.get_json()
    return jsonify({"message": "Indexing request received", "data": data}), 202

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
