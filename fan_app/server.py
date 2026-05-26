#!/usr/bin/env python3
"""
Servidor fan-cam — 3 son Multitud

Uso local (red WiFi del casino):
    pip install flask
    python server.py

Luego genera el QR con la IP local:
    python generar_qr.py --url http://192.168.1.XX:5001

IMPORTANTE: iOS Safari requiere HTTPS para acceder a la cámara.
Para HTTPS gratuito usa ngrok:
    ngrok http 5001
    python generar_qr.py --url https://xxxx.ngrok.io

Ver solicitudes de canciones (desde el celular de la banda):
    http://localhost:5001/api/solicitudes?token=banda3sm
"""

import os
import sqlite3
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)
DB_PATH = Path(__file__).parent / "solicitudes.db"
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "banda3sm")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS solicitudes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre    TEXT DEFAULT 'Anónimo',
            cancion   TEXT NOT NULL,
            creado_en TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    conn.close()


@app.route("/")
def index():
    return send_from_directory(Path(__file__).parent, "index.html")


@app.route("/api/solicitud", methods=["POST"])
def recibir():
    data = request.get_json(silent=True) or {}
    nombre  = (data.get("nombre") or "Anónimo").strip()[:80]
    cancion = (data.get("cancion") or "").strip()[:120]
    if not cancion:
        return jsonify({"ok": False, "error": "Canción requerida"}), 400
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO solicitudes (nombre, cancion) VALUES (?,?)", (nombre, cancion))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "mensaje": f"¡Gracias {nombre}! Vamos a tocar '{cancion}' 🎵"})


@app.route("/api/solicitudes")
def ver():
    if request.args.get("token", "") != ADMIN_TOKEN:
        return jsonify({"error": "No autorizado"}), 401
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, nombre, cancion, creado_en FROM solicitudes ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify([{"id": r[0], "nombre": r[1], "cancion": r[2], "hora": r[3]} for r in rows])


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5001))
    print(f"
🎸  Fan-cam 3 son Multitud  —  http://localhost:{port}")
    print(f"📋  Ver solicitudes         —  http://localhost:{port}/api/solicitudes?token={ADMIN_TOKEN}
")
    app.run(host="0.0.0.0", port=port, debug=False)
