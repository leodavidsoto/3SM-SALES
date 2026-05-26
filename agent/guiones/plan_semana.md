# Plan Semanal — 3 son Multitud
**Objetivo:** 20 correos enviados · 10 llamadas · 3–5 reels publicados · 2–3 leads calientes

---

## LUNES — Carga y productoras

### Mañana (9:00–12:00h)
- [ ] `cd agent && python seeds/cargar_seeds.py` — cargar prospectos
- [ ] `python main.py generar --tipo productora`
- [ ] `python main.py generar --tipo boda`
- [ ] Revisar correos: `python main.py ver <id>`
- [ ] Enviar a: Agencia Click · F.Producciones · LaPizarra · Zitta · AVAD

### Tarde (15:00–18:00h)
- [ ] Llamar Magdalena Tapia — Agencia Click: **+56 2 2638 3686**
- [ ] Llamar F.Producciones: **+56 9 6538 3591**
- [ ] DM Instagram: @agenciaclick · @somoslapizarra
- [ ] Grabar Reel 1 (Casino Enjoy reveal)
- [ ] `python main.py stats` — estado inicial

---

## MARTES — Hoteles y centros culturales

### Mañana (9:00–12:00h)
- [ ] `python main.py generar --tipo hotel`
- [ ] `python main.py generar --tipo municipal`
- [ ] Enviar 5 correos: W Santiago · Mandarin · Ritz-Carlton · Cumbres · NH Collection
- [ ] Correo GAM + Municipalidad de Providencia y Las Condes
- [ ] Correo ANAWEP: anawepchile@gmail.com

### Tarde (15:00–18:00h)
- [ ] **Publicar Reel 1** (20:00h)
- [ ] Llamar GAM: Coordinador de Programación
- [ ] Llamar Municipalidad de Providencia: Coordinador de Cultura

---

## MIÉRCOLES — Empresas y casinos

### Mañana (9:00–12:00h)
- [ ] `python main.py generar --tipo empresa`
- [ ] `python main.py generar --tipo casino`
- [ ] Enviar 5 correos: BancoEstado · Entel · CODELCO · Latam · Claro
- [ ] Correo Casino Dreams: servicioalcliente@dreams.cl
- [ ] `python main.py seguimientos` — revisar follow-ups

### Tarde (15:00–18:00h)
- [ ] **Publicar Reel 2** (20:00h)
- [ ] Grabar Reel 3 o 4
- [ ] Follow-up WhatsApp contactos del lunes sin respuesta

---

## JUEVES — SHOW + mañana de seguimientos

### Mañana (9:00–13:00h)
- [ ] Revisar respuestas email → `python main.py marcar <id> --respondido`
- [ ] `python main.py generar --tipo educacion`
- [ ] Enviar 5 correos: U. Chile · UC · UDP · UAI · DUOC
- [ ] Follow-up WhatsApp a contactos sin respuesta

### Noche — Show Casino Enjoy (21:00h+)
- [ ] Grabar 3–5 clips para reels
- [ ] Activar QR fan-cam durante el show
- [ ] Stories en @3smultitud y @luomina

---

## VIERNES — SHOW + llamadas

### Mañana (9:00–13:00h)
- [ ] **Publicar Reel 3** (12:00h)
- [ ] Llamar Sebastián LaPizarra: **+56 9 5841 9326**
- [ ] Llamar AVAD Eventos: **+56 9 9362 3059**
- [ ] Responder leads calientes

### Noche — Show Casino Enjoy (21:00h+)
- [ ] Grabar closing shot y crowd reaction
- [ ] Cross-post Stories @luomina → @3smultitud
- [ ] Activar fan-cam QR

---

## SÁBADO — SHOW + behind the scenes

### Tarde (antes del show)
- [ ] **Publicar Reel 4** (12:00h — peak fin de semana)
- [ ] Grabar Reel 5 (preparación pre-show)

### Noche — Show Casino Enjoy (21:00h+)
- [ ] Grabar contenido para la semana siguiente
- [ ] Activar fan-cam QR
- [ ] Stories en tiempo real

---

## DOMINGO — Cierre y planificación

### Tarde (15:00–18:00h)
- [ ] `python main.py stats` — métricas de la semana
- [ ] `python main.py seguimientos` — programar próxima semana
- [ ] **Publicar Reel 5** (19:00h)
- [ ] Editar mejores clips del fin de semana
- [ ] Anotar leads que respondieron → preparar propuesta

---

## MÉTRICAS SEMANALES

| Métrica | Meta |
|---|---|
| Correos enviados | 20 |
| Respuestas | 3–5 (15–25%) |
| Llamadas | 10 |
| Leads calientes | 2–3 |
| Reels publicados | 3–5 |
| Solicitudes fan-cam | 10+ |

---

## COMANDOS RÁPIDOS

```bash
python seeds/cargar_seeds.py
python main.py generar --tipo [casino|productora|boda|empresa|hotel|municipal|educacion]
python main.py ver <id>
python main.py marcar <id> --enviado
python main.py marcar <id> --respondido
python main.py stats
python main.py seguimientos
```
