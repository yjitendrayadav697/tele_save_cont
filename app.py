"""
app.py
Minimal Flask keep-alive server.
Only exposes a health-check endpoint — no sensitive data.
"""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/")
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
