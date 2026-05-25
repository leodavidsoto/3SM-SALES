import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "prospectos.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS prospectos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT NOT NULL,
            tipo        TEXT NOT NULL CHECK(tipo IN ('casino','empresa','boda','productora')),
            ciudad      TEXT,
            email       TEXT,
            telefono    TEXT,
            contacto    TEXT,
            cargo       TEXT,
            fuente      TEXT,
            creado_en   TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS correos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            prospecto_id    INTEGER NOT NULL REFERENCES prospectos(id),
            asunto          TEXT,
            cuerpo          TEXT NOT NULL,
            enviado         INTEGER DEFAULT 0,
            enviado_en      TEXT,
            abierto         INTEGER DEFAULT 0,
            respondido      INTEGER DEFAULT 0,
            creado_en       TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS seguimientos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            prospecto_id    INTEGER NOT NULL REFERENCES prospectos(id),
            fecha_prog      TEXT NOT NULL,
            nota            TEXT,
            completado      INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


def add_prospecto(nombre, tipo, ciudad="", email="", telefono="", contacto="", cargo="", fuente="manual"):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO prospectos (nombre,tipo,ciudad,email,telefono,contacto,cargo,fuente) VALUES (?,?,?,?,?,?,?,?)",
        (nombre, tipo, ciudad, email, telefono, contacto, cargo, fuente),
    )
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid


def save_correo(prospecto_id, asunto, cuerpo):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO correos (prospecto_id, asunto, cuerpo) VALUES (?,?,?)",
        (prospecto_id, asunto, cuerpo),
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def mark_enviado(correo_id):
    conn = get_conn()
    conn.execute(
        "UPDATE correos SET enviado=1, enviado_en=datetime('now','localtime') WHERE id=?",
        (correo_id,),
    )
    conn.commit()
    conn.close()


def mark_respondido(correo_id):
    conn = get_conn()
    conn.execute("UPDATE correos SET respondido=1 WHERE id=?", (correo_id,))
    conn.commit()
    conn.close()


def add_seguimiento(prospecto_id, dias=3, nota=""):
    from datetime import timedelta
    fecha = (date.today() + timedelta(days=dias)).isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO seguimientos (prospecto_id, fecha_prog, nota) VALUES (?,?,?)",
        (prospecto_id, fecha, nota),
    )
    conn.commit()
    conn.close()


def get_pendientes_seguimiento():
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.id, s.fecha_prog, s.nota, p.nombre, p.email, p.tipo
        FROM seguimientos s
        JOIN prospectos p ON p.id = s.prospecto_id
        WHERE s.completado=0 AND s.fecha_prog <= date('now','localtime')
        ORDER BY s.fecha_prog
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_conn()
    stats = {}
    stats["total_prospectos"] = conn.execute("SELECT COUNT(*) FROM prospectos").fetchone()[0]
    stats["correos_generados"] = conn.execute("SELECT COUNT(*) FROM correos").fetchone()[0]
    stats["correos_enviados"] = conn.execute("SELECT COUNT(*) FROM correos WHERE enviado=1").fetchone()[0]
    stats["respondidos"] = conn.execute("SELECT COUNT(*) FROM correos WHERE respondido=1").fetchone()[0]
    stats["seguimientos_pendientes"] = conn.execute(
        "SELECT COUNT(*) FROM seguimientos WHERE completado=0"
    ).fetchone()[0]
    por_tipo = conn.execute(
        "SELECT tipo, COUNT(*) as n FROM prospectos GROUP BY tipo"
    ).fetchall()
    stats["por_tipo"] = {r["tipo"]: r["n"] for r in por_tipo}
    conn.close()
    return stats


def list_prospectos(tipo=None, sin_correo=False):
    conn = get_conn()
    query = "SELECT * FROM prospectos"
    params = []
    clauses = []
    if tipo:
        clauses.append("tipo=?")
        params.append(tipo)
    if sin_correo:
        clauses.append("id NOT IN (SELECT DISTINCT prospecto_id FROM correos)")
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
