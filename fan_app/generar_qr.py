#!/usr/bin/env python3
"""
Genera el QR code para la fan-cam.

Uso:
    pip install qrcode[pil]
    python generar_qr.py --url https://xxxx.ngrok.io
"""
import click


@click.command()
@click.option("--url", required=True, help="URL de la fan-cam")
@click.option("--output", default="qr_fancam.png", show_default=True)
def generar(url, output):
    try:
        import qrcode
    except ImportError:
        click.echo("Instala qrcode: pip install qrcode[pil]")
        raise SystemExit(1)

    qr = qrcode.QRCode(box_size=12, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output)
    click.echo(f"✓ QR generado: {output}")
    click.echo(f"  URL: {url}")
    click.echo("\nProjecta el QR en pantalla o imprímelo en A4 para mostrarlo en el escenario.")


if __name__ == "__main__":
    generar()
