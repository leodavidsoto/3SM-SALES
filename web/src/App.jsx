import React, { useState, useEffect } from 'react'
import { uploadFile, createOrder } from './api' // listOrders ya no se usa en el cliente

/* ========= util ========= */
const fmtCLP = (n) => new Intl.NumberFormat('es-CL', { style:'currency', currency:'CLP', maximumFractionDigits:0 }).format(Number(n||0))

const BANK = {
  banco: 'Tenpo Prepago',
  tipo: 'Cuenta Vista',
  numero: '1111113921878',
  titular: 'Rodrigo Reyes',
  rut: '13.921.878-7',
  correo: 'pagos@impresionessos.cl' // opcional
}

/* ========= UI base ========= */
function Section({ title, children }) {
  return (
    <section className="glass p-6 md:p-8 space-y-4">
      <h2 className="text-lg md:text-xl font-semibold tracking-wide text-brand-300">{title}</h2>
      {children}
    </section>
  )
}
function Select({ label, value, onChange, options }) {
  const items = options.map(o => typeof o === 'string' ? {label:o, value:o} : o)
  return (
    <label className="block space-y-2">
      <span className="text-slate-300 text-sm">{label}</span>
      <div className="glass p-2">
        <select className="w-full bg-transparent outline-none" value={value} onChange={e=>onChange(e.target.value)}>
          {items.map(i => <option key={i.value} value={i.value}>{i.label}</option>)}
        </select>
      </div>
    </label>
  )
}
function NumberInput({ label, value, onChange, min=0 }) {
  return (
    <label className="block space-y-2">
      <span className="text-slate-300 text-sm">{label}</span>
      <input type="number" min={min} value={value} onChange={e=>onChange(e.target.value)} className="glass w-full p-2 bg-transparent outline-none" />
    </label>
  )
}

/* ========= MODAL ========= */
function OrderModal({ open, onClose, order, analysis }) {
  if (!open || !order) return null
  const textoTransferencia =
`Banco: ${BANK.banco}
Tipo de cuenta: ${BANK.tipo}
N° de cuenta: ${BANK.numero}
Titular: ${BANK.titular}
RUT: ${BANK.rut}
${BANK.correo ? `Correo: ${BANK.correo}\n` : ''}Monto: ${fmtCLP(order.total)}
Asunto/Mensaje: Orden #${order.id}`

  const copiar = async (txt) => { try { await navigator.clipboard.writeText(txt) } catch {} }

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-xs" onClick={onClose} />
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="glass w-full max-w-xl relative overflow-hidden">
          <div className="pointer-events-none absolute -top-20 -right-20 h-60 w-60 rounded-full blur-3xl opacity-30"
               style={{ background: "radial-gradient(circle at 30% 30%, #0D8FFF, transparent 60%)" }} />
          <div className="p-6 md:p-8 relative space-y-5">
            <div className="flex items-start justify-between gap-4">
              <h3 className="font-display text-xl md:text-2xl neon">Orden creada</h3>
              <button onClick={onClose} className="glass px-3 py-1 text-sm hover:bg-white/10">Cerrar</button>
            </div>

            <div className="grid gap-3">
              <div className="glass p-4">
                <p className="text-xs text-slate-400">N° de Orden</p>
                <p className="font-semibold">#{order.id}</p>
              </div>
              <div className="glass p-4">
                <p className="text-xs text-slate-400">Total</p>
                <p className="font-semibold">{fmtCLP(order.total)}</p>
              </div>
              {analysis && (
                <div className="glass p-4">
                  <p className="text-xs text-slate-400">Detalle detectado</p>
                  <p className="font-medium">
                    {analysis.pages} pág. — {analysis.pagesWithImages} con imágenes — {analysis.isTextOnly ? 'Solo texto' : 'Con imágenes'}
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-3">
              <h4 className="text-brand-200 font-semibold">Pago por transferencia</h4>
              <div className="glass p-4 space-y-2 text-sm">
                <p><span className="text-slate-400">Banco:</span> {BANK.banco}</p>
                <p><span className="text-slate-400">Tipo de cuenta:</span> {BANK.tipo}</p>
                <p><span className="text-slate-400">N° de cuenta:</span> <span className="font-semibold">{BANK.numero}</span></p>
                <p><span className="text-slate-400">Titular:</span> {BANK.titular}</p>
                <p><span className="text-slate-400">RUT:</span> {BANK.rut}</p>
                {BANK.correo && <p><span className="text-slate-400">Correo:</span> {BANK.correo}</p>}
                <p><span className="text-slate-400">Monto:</span> <span className="font-semibold">{fmtCLP(order.total)}</span></p>
                <p><span className="text-slate-400">Asunto/Mensaje:</span> Orden #{order.id}</p>
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => copiar(textoTransferencia)}
                  className="inline-flex h-11 items-center justify-center px-4 rounded-xl
                             bg-brand-500/30 border border-brand-400/40 hover:bg-brand-500/40
                             transition text-brand-50 font-semibold"
                >
                  Copiar datos de transferencia
                </button>
                {BANK.correo && (
                  <a
                    href={`mailto:${BANK.correo}?subject=Comprobante%20Orden%20%23${order.id}&body=Adjunto%20comprobante%20de%20transferencia%20por%20${encodeURIComponent(fmtCLP(order.total))}.`}
                    className="inline-flex h-11 items-center justify-center px-4 rounded-xl glass hover:bg-white/10"
                  >
                    Enviar comprobante
                  </a>
                )}
              </div>
              <p className="text-xs text-slate-400">
                * Una vez realizada la transferencia, adjunta el comprobante indicando el número de orden.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ========= APP ========= */
export default function App() {
  const [fileInfo, setFileInfo] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Datos del cliente (incluye dirección)
  const [form, setForm] = useState({
    customer_name: '', email: '', phone: '',
    address: '', // ✅ NUEVO: dirección para delivery
    notes: ''
  })

  // Parámetros de impresión
  const [params, setParams] = useState({
    // ❌ paper_size eliminado
    color_mode: 'BN',
    duplex: 'simplex',
    paper_type: 'normal75', // ✅ NUEVO: tipo de papel
    anillado: 'none',       // ✅ reemplaza a encuadernado
    photo_size: 'none',
    copies: 1,
    delivery: 'normal',
    desired_date: ''        // ✅ NUEVO: calendario (fecha)
  })

  async function onUpload(e) {
    const f = e.target.files?.[0]
    if (!f) return
    setLoading(true)
    try {
      const res = await uploadFile(f)
      setFileInfo(res.file)
      setAnalysis(res.analysis)
    } catch (e) {
      alert(`No se pudo analizar el archivo: ${e.message}`)
      setFileInfo(null); setAnalysis(null)
    } finally { setLoading(false) }
  }

  async function onSubmitOrder() {
    if (!fileInfo) return alert('Sube un archivo primero')
    if (!form.customer_name) return alert('Ingresa tu nombre')
    if (params.desired_date === '') return alert('Elige una fecha para agendar')
    setSubmitting(true)
    try {
      const payload = {
        ...form,
        file: fileInfo,
        params: {
          ...params,
          copies: Number(params.copies) || 1
        }
      }
      const res = await createOrder(payload)
      // Mostrar modal bonito
      setLastOrder({ id: res.order_id, total: res.total })
      setModalOpen(true)
    } catch (e) {
      alert(`No se pudo crear la orden: ${e.message}`)
    } finally { setSubmitting(false) }
  }

  const [modalOpen, setModalOpen] = useState(false)
  const [lastOrder, setLastOrder] = useState(null)

  return (
    <div className="relative min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 text-slate-100">
      {/* decoraciones neon */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-24 -right-24 h-72 w-72 rounded-full blur-3xl opacity-30"
             style={{ background: "radial-gradient(circle at 30% 30%, #0D8FFF, transparent 60%)" }} />
        <div className="absolute bottom-0 left-0 h-80 w-80 rounded-full blur-3xl opacity-20"
             style={{ background: "radial-gradient(circle at 70% 70%, #22d3ee, transparent 60%)" }} />
      </div>

      <header className="max-w-6xl mx-auto px-4 sm:px-6 pt-10 pb-6">
        <div className="flex items-center gap-3">
          <img src="/logo.png" alt="Impresiones SOS" className="h-12 md:h-14 w-auto rounded-xl glass p-1" />
          <div>
            <h1 className="font-display text-2xl md:text-3xl neon">Impresiones SOS</h1>
            <p className="text-slate-300 text-sm md:text-base">Cotiza y envía tus archivos con acabado profesional</p>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 pb-20 space-y-6 md:space-y-8">
        {/* 1) Archivo */}
        <Section title="1) Archivo">
          <div className="flex flex-col md:flex-row items-start md:items-center gap-4">
            <label className="glass p-4 cursor-pointer inline-flex items-center gap-3 hover:border-brand-400/50 transition">
              <input type="file" className="hidden" onChange={onUpload} accept=".pdf,image/*,.txt,.doc,.docx" />
              <span className="inline-flex h-9 px-4 items-center justify-center rounded-lg bg-brand-500/20 border border-brand-400/30 text-brand-200 font-semibold">
                Seleccionar archivo
              </span>
              <span className="text-slate-300">{fileInfo ? fileInfo.name : "PDF/Imagen/DOC..."}</span>
            </label>
            {loading && <span className="text-brand-300 animate-pulse">Analizando archivo...</span>}
          </div>

          {fileInfo && analysis && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="glass p-4">
                <p className="text-xs text-slate-400">Tipo</p>
                <p className="font-semibold text-slate-100">{fileInfo.mimeType}</p>
              </div>
              <div className="glass p-4">
                <p className="text-xs text-slate-400">Páginas</p>
                <p className="font-semibold">{analysis.pages}</p>
              </div>
              <div className="glass p-4">
                <p className="text-xs text-slate-400">Con imágenes (est.)</p>
                <p className="font-semibold">{analysis.pagesWithImages}</p>
              </div>
              <div className="glass p-4">
                <p className="text-xs text-slate-400">¿Solo texto?</p>
                <p className="font-semibold">{analysis.isTextOnly ? 'Sí' : 'No'}</p>
              </div>
            </div>
          )}
        </Section>

        {/* 2) Datos del cliente */}
        <Section title="2) Datos del cliente">
          <div className="grid md:grid-cols-2 gap-4">
            <input className="glass p-3 outline-none" placeholder="Nombre"
                   value={form.customer_name} onChange={e=>setForm({...form, customer_name: e.target.value})}/>
            <input className="glass p-3 outline-none" placeholder="Email"
                   value={form.email} onChange={e=>setForm({...form, email: e.target.value})}/>
            <input className="glass p-3 outline-none" placeholder="Teléfono"
                   value={form.phone} onChange={e=>setForm({...form, phone: e.target.value})}/>
            <input className="glass p-3 outline-none" placeholder="Dirección (para delivery)"
                   value={form.address} onChange={e=>setForm({...form, address: e.target.value})}/>
            <input className="glass p-3 outline-none md:col-span-2" placeholder="Notas"
                   value={form.notes} onChange={e=>setForm({...form, notes: e.target.value})}/>
          </div>
        </Section>

        {/* 3) Parámetros de impresión */}
        <Section title="3) Parámetros de impresión">
          <div className="grid md:grid-cols-3 gap-4">
            {/* ❌ Tamaño papel eliminado */}
            <Select label="Color" value={params.color_mode}
                    onChange={v=>setParams({...params, color_mode: v})}
                    options={[{label:'B/N',value:'BN'},{label:'Color',value:'Color'}]} />
            <Select label="Dúplex" value={params.duplex}
                    onChange={v=>setParams({...params, duplex: v})}
                    options={[{label:'Simple',value:'simplex'},{label:'Doble faz',value:'duplex'}]} />
            <Select label="Tipo de papel" value={params.paper_type}
                    onChange={v=>setParams({...params, paper_type: v})}
                    options={[
                      {label:'Normal (75g)', value:'normal75'},
                      {label:'Opalina lisa (200g)', value:'opalina200'}
                    ]} />
            <Select label="Anillado" value={params.anillado}
                    onChange={v=>setParams({...params, anillado: v})}
                    options={[
                      {label:'Sin anillar', value:'none'},
                      {label:'Anillado plástico', value:'plastico'},
                      {label:'Anillado metálico', value:'metalico'}
                    ]} />
            <Select label="Tamaño foto" value={params.photo_size}
                    onChange={v=>setParams({...params, photo_size: v})}
                    options={[
                      {label:'Sin foto', value:'none'},
                      {label:'Pequeña', value:'small'},
                      {label:'Mediana', value:'medium'},
                      {label:'Grande', value:'large'}
                    ]} />
            <NumberInput label="Copias" value={params.copies}
                         onChange={v=>setParams({...params, copies: v})} min={1}/>
            <Select label="Delivery" value={params.delivery}
                    onChange={v=>setParams({...params, delivery: v})}
                    options={[
                      {label:'Retiro en tienda', value:'retiro'},
                      {label:'Normal', value:'normal'},
                      {label:'Express', value:'express'}
                    ]} />
            {/* ✅ Calendario para agenda */}
            <label className="block space-y-2">
              <span className="text-slate-300 text-sm">¿Para cuándo quieres tus impresiones?</span>
              <input type="date" className="glass w-full p-2 bg-transparent outline-none"
                     value={params.desired_date}
                     onChange={e=>setParams({...params, desired_date: e.target.value})}/>
            </label>
          </div>
        </Section>

        {/* Botón de confirmación */}
        <div className="flex items-center gap-4">
          <button
            onClick={onSubmitOrder}
            disabled={submitting}
            className="relative inline-flex h-11 items-center justify-center px-6 rounded-xl
                       bg-brand-500/30 border border-brand-400/40 hover:bg-brand-500/40
                       transition text-brand-50 font-semibold disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {submitting ? 'Creando orden...' : 'Confirmar orden'}
          </button>
          <p className="text-slate-300 text-sm">* Verás el total y datos de pago al crear la orden.</p>
        </div>
      </main>

      {/* MODAL */}
      <OrderModal open={modalOpen} onClose={()=>setModalOpen(false)} order={lastOrder} analysis={analysis} />

      <footer className="max-w-6xl mx-auto px-4 sm:px-6 py-10 text-xs text-slate-400">
        © {new Date().getFullYear()} Impresiones SOS
      </footer>
    </div>
  )
}
