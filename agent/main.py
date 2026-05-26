#!/usr/bin/env python3
"""
Agente de Prospección y Ventas — 3 son Multitud
Uso:
    python main.py buscar  --tipo casino --ciudad Santiago --n 20
    python main.py buscar  --tipo hotel --ciudad Santiago --n 15
    python main.py generar --tipo casino
    python main.py stats
    python main.py seguimientos
    python main.py add     --nombre "Casino X" --tipo casino --email foo@bar.com --ciudad Viña

Tipos disponibles: casino, empresa, boda, productora, hotel, municipal, educacion
"""

import click
from rich.console import Console
from rich.table import Table
from rich import box

import crm
import scraper
import llm_generator

console = Console()

TIPOS = ["casino", "empresa", "boda", "productora", "hotel", "municipal", "educacion"]


@click.group()
def cli():
    """Agente de ventas — 3 son Multitud"""
    crm.init_db()


@cli.command()
@click.option("--tipo", required=True, type=click.Choice(TIPOS))
@click.option("--ciudad", required=True)
@click.option("--n", default=20, show_default=True, help="Máximo de resultados")
@click.option("--guardar/--no-guardar", default=True, help="Guardar leads en CRM")
def buscar(tipo, ciudad, n, guardar):
    """Busca prospectos y los guarda en el CRM."""
    console.print(f"[bold cyan]Buscando {n} leads de tipo '[yellow]{tipo}[/yellow]' en {ciudad}...[/bold cyan]")
    leads = scraper.buscar_leads(tipo, ciudad, n)

    if not leads:
        console.print("[red]No se encontraron leads.[/red]")
        return

    table = Table(title=f"Leads encontrados ({len(leads)})", box=box.SIMPLE)
    table.add_column("Nombre", style="white")
    table.add_column("Email", style="cyan")
    table.add_column("Teléfono", style="green")
    table.add_column("Fuente", style="dim")

    saved = 0
    for lead in leads:
        table.add_row(
            lead["nombre"][:50],
            lead.get("email", "") or "—",
            lead.get("telefono", "") or "—",
            lead.get("fuente", "")[:30],
        )
        if guardar:
            crm.add_prospecto(
                nombre=lead["nombre"],
                tipo=tipo,
                ciudad=lead.get("ciudad", ciudad),
                email=lead.get("email", ""),
                telefono=lead.get("telefono", ""),
                contacto=lead.get("contacto", ""),
                cargo=lead.get("cargo", ""),
                fuente=lead.get("fuente", ""),
            )
            saved += 1

    console.print(table)
    if guardar:
        console.print(f"[bold green]✓ {saved} leads guardados en el CRM.[/bold green]")


@cli.command()
@click.option("--nombre", required=True)
@click.option("--tipo", required=True, type=click.Choice(TIPOS))
@click.option("--ciudad", default="")
@click.option("--email", default="")
@click.option("--telefono", default="")
@click.option("--contacto", default="", help="Nombre de la persona de contacto")
@click.option("--cargo", default="")
def add(nombre, tipo, ciudad, email, telefono, contacto, cargo):
    """Agrega un prospecto manualmente al CRM."""
    pid = crm.add_prospecto(nombre, tipo, ciudad, email, telefono, contacto, cargo, fuente="manual")
    console.print(f"[bold green]✓ Prospecto #{pid} '{nombre}' agregado.[/bold green]")


@cli.command()
@click.option("--tipo", default=None, type=click.Choice(TIPOS))
@click.option("--id", "prospecto_id", default=None, type=int, help="ID específico de prospecto")
@click.option("--seguimiento/--no-seguimiento", default=True, help="Programar follow-up a 3 días")
def generar(tipo, prospecto_id, seguimiento):
    """Genera correos personalizados para prospectos sin correo."""
    if prospecto_id:
        conn = crm.get_conn()
        row = conn.execute("SELECT * FROM prospectos WHERE id=?", (prospecto_id,)).fetchone()
        conn.close()
        if not row:
            console.print(f"[red]No existe prospecto con id={prospecto_id}[/red]")
            return
        prospectos = [dict(row)]
    else:
        prospectos = crm.list_prospectos(tipo=tipo, sin_correo=True)

    if not prospectos:
        console.print("[yellow]No hay prospectos pendientes de correo.[/yellow]")
        return

    console.print(f"[bold cyan]Generando correos para {len(prospectos)} prospecto(s)...[/bold cyan]")
    resultados = llm_generator.generar_lote(prospectos)

    ok = 0
    for r in resultados:
        pid = r["prospecto_id"]
        if r["ok"]:
            cid = crm.save_correo(pid, r["asunto"], r["cuerpo"])
            if seguimiento:
                crm.add_seguimiento(pid, dias=3, nota="Follow-up inicial")
            console.print(f"  [green]✓[/green] Prospecto #{pid} → correo #{cid} — [bold]{r['asunto']}[/bold]")
            ok += 1
        else:
            console.print(f"  [red]✗[/red] Prospecto #{pid} — Error: {r['error']}")

    console.print(f"\n[bold green]{ok}/{len(prospectos)} correos generados.[/bold green]")


@cli.command()
@click.argument("correo_id", type=int)
def ver(correo_id):
    """Muestra el contenido de un correo generado."""
    conn = crm.get_conn()
    row = conn.execute(
        "SELECT c.*, p.nombre, p.email FROM correos c JOIN prospectos p ON p.id=c.prospecto_id WHERE c.id=?",
        (correo_id,),
    ).fetchone()
    conn.close()
    if not row:
        console.print(f"[red]Correo #{correo_id} no encontrado.[/red]")
        return
    r = dict(row)
    console.rule(f"[bold]Correo #{correo_id} → {r['nombre']} ({r['email'] or 'sin email'})")
    console.print(f"[bold]Asunto:[/bold] {r['asunto']}\n")
    console.print(r["cuerpo"])
    console.rule()


@cli.command()
def stats():
    """Muestra el resumen del CRM."""
    s = crm.get_stats()
    table = Table(title="Estado del CRM — 3 son Multitud", box=box.ROUNDED)
    table.add_column("Métrica", style="bold white")
    table.add_column("Valor", justify="right", style="cyan")

    table.add_row("Total prospectos", str(s["total_prospectos"]))
    table.add_row("Correos generados", str(s["correos_generados"]))
    table.add_row("Correos enviados", str(s["correos_enviados"]))
    table.add_row("Respuestas recibidas", str(s["respondidos"]))
    table.add_row("Seguimientos pendientes", str(s["seguimientos_pendientes"]))

    if s["total_prospectos"] > 0 and s["correos_enviados"] > 0:
        tasa = round(s["respondidos"] / s["correos_enviados"] * 100, 1)
        table.add_row("Tasa de respuesta", f"{tasa}%")

    console.print(table)

    if s["por_tipo"]:
        t2 = Table(title="Por nicho", box=box.SIMPLE)
        t2.add_column("Nicho")
        t2.add_column("Prospectos", justify="right")
        for tipo, n in s["por_tipo"].items():
            t2.add_row(tipo, str(n))
        console.print(t2)


@cli.command()
def seguimientos():
    """Lista los follow-ups pendientes para hoy."""
    pendientes = crm.get_pendientes_seguimiento()
    if not pendientes:
        console.print("[green]No hay seguimientos pendientes para hoy.[/green]")
        return

    table = Table(title=f"Seguimientos pendientes ({len(pendientes)})", box=box.SIMPLE)
    table.add_column("Fecha")
    table.add_column("Prospecto", style="bold")
    table.add_column("Email", style="cyan")
    table.add_column("Nicho")
    table.add_column("Nota")

    for s in pendientes:
        table.add_row(s["fecha_prog"], s["nombre"], s["email"] or "—", s["tipo"], s["nota"] or "—")

    console.print(table)


@cli.command()
@click.argument("correo_id", type=int)
@click.option("--enviado/--no-enviado", default=False)
@click.option("--respondido/--no-respondido", default=False)
def marcar(correo_id, enviado, respondido):
    """Actualiza el estado de un correo (enviado / respondido)."""
    if enviado:
        crm.mark_enviado(correo_id)
        console.print(f"[green]✓ Correo #{correo_id} marcado como enviado.[/green]")
    if respondido:
        crm.mark_respondido(correo_id)
        console.print(f"[green]✓ Correo #{correo_id} marcado como respondido.[/green]")


if __name__ == "__main__":
    cli()
