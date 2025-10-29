from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Ingestion Service is running"}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    # Important: Use host='0.0.0.0' to make it accessible from outside the container
    app.run(host='0.0.0.0', port=8000)
