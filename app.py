"""Local Flask app: serves the showcase page and the live chat / confirm API."""
import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # never download - use the cached model

from flask import Flask, jsonify, request, send_from_directory

import assistant

app = Flask(__name__)
ROOT = os.path.dirname(os.path.abspath(__file__))


@app.get("/")
def index():
    return send_from_directory(os.path.join(ROOT, "templates"), "index.html")


@app.get("/web/<path:name>")
def web_files(name):
    return send_from_directory(os.path.join(ROOT, "web"), name)


@app.get("/api/health")
def health():
    return jsonify(ok=True, model=assistant.MODEL_ID)


@app.post("/api/chat")
def chat():
    body = request.get_json(silent=True) or {}
    message = str(body.get("message", "")).strip()
    if not message:
        return jsonify(error="empty message"), 400
    return jsonify(assistant.handle(message, simulate_outage=bool(body.get("simulate_outage"))))


@app.post("/api/confirm")
def confirm():
    body = request.get_json(silent=True) or {}
    return jsonify(assistant.confirm(str(body.get("id", "")), bool(body.get("approve"))))


if __name__ == "__main__":
    assistant.load()  # load the model before the first request
    app.run(port=5000, debug=False)
