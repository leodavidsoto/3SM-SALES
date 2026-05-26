#!/usr/bin/env python3
"""
Carga los prospectos del CSV al CRM.

Uso:
    cd agent
    python seeds/cargar_seeds.py
    python seeds/cargar_seeds.py --preview       # solo muestra, no guarda
    python seeds/cargar_seeds.py --tipo casino   # solo un nicho
"""
import csv
import sys
import os
import click
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import crm

CSV_PATH = Path(__file__).parent / "prospectos.csv"


@click.command()
@click.option("--preview", is_flag=True, help="Solo muestra los prospectos, no guarda")
@click.option("--tipo", default=None, help="Filtrar por tipo")
def cargar(preview, tipo):
    crm.init_db()

    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if tipo:
        rows = [r for r in rows if r["tipo"].lower() == tipo.lower()]

    print(f"\n{'PREVIEW' if preview else 'CARGANDO'} — {len(rows)} prospectos\n")
    print(f"{'TIPO':<12} {'NOMBRE':<40} {'EMAIL':<35} {'CIUDAD'}")
    print("-" * 100)

    cargados = 0
    for r in rows:
        print(f"{r['tipo']:<12} {r['nombre'][:38]:<40} {r['email'][:33]:<35} {r['ciudad']}")
        if not preview:
            conn = crm.get_conn()
            existe = conn.execute(
                "SELECT id FROM prospectos WHERE nombre=?", (r["nombre"],)
            ).fetchone()
            conn.close()
            if existe:
                print(f"  → Ya existe, se omite.")
                continue
            crm.add_prospecto(
                nombre=r["nombre"],
                tipo=r["tipo"],
                ciudad=r["ciudad"],
                email=r["email"],
                telefono=r["telefono"],
                contacto=r["contacto"],
                cargo=r["cargo"],
                fuente=r.get("fuente", "seed"),
            )
            cargados += 1

    if not preview:
        print(f"\n✓ {cargados} prospectos nuevos cargados al CRM.")
    else:
        print(f"\n→ Preview completado. Ejecuta sin --preview para cargar.")


if __name__ == "__main__":
    cargar()
