import express from 'express'
import multer from 'multer'
import fs from 'fs'
import path from 'path'
import Database from 'better-sqlite3'
import dotenv from 'dotenv'
import { execFile } from 'child_process'
import { promisify } from 'util'
import cors from 'cors'
import mime from 'mime-types'

dotenv.config()
const execFileAsync = promisify(execFile)

const app = express()
const PORT = process.env.PORT || 4000
const UPLOAD_DIR = path.join(process.cwd(), 'uploads')
if (!fs.existsSync(UPLOAD_DIR)) fs.mkdirSync(UPLOAD_DIR, { recursive: true })

// ===== Middlewares base =====
app.use(express.json())

// CORS fuerte (permite consumir desde Vercel/iOS)
app.use(
  cors({
    origin: '*',
    methods: ['GET', 'POST', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization'],
  })
)

// Servir /uploads con headers compatibles iOS (PDF inline, CORS, CORP)
app.use(
  '/uploads',
  (req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', '*')
    res.setHeader('Cross-Origin-Resource-Policy', 'cross-origin')
    res.setHeader('Cross-Origin-Opener-Policy', 'same-origin-allow-popups')
    res.setHeader('Cross-Origin-Embedder-Policy', 'unsafe-none')
    next()
  },
  express.static(UPLOAD_DIR, {
    setHeaders: (res, filePath) => {
      const type = mime.lookup(filePath) || 'application/octet-stream'
      res.setHeader('Content-Type', type)
      // iOS prefiere inline para visualizar PDFs en visor nativo
      if (type === 'application/pdf') {
        res.setHeader('Content-Disposition', 'inline')
      }
      res.setHeader('Cache-Control', 'public, max-age=3600')
    },
  })
)

// ===== Multer (subidas) =====
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, UPLOAD_DIR),
  filename: (req, file, cb) => {
    const unique = Date.now() + '-' + Math.round(Math.random() * 1e9)
    cb(null, unique + '-' + file.originalname.replace(/\s+/g, '_'))
  },
})
const upload = multer({ storage })

// ===== DB =====
const db = new Database(path.join(process.cwd(), 'impr.db'))
db.pragma('journal_mode = WAL')
db.prepare(`
  CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    notes TEXT,
    file_name TEXT,
    file_mime TEXT,
    file_size INTEGER,
    params_json TEXT,
    desired_date TEXT,
    payment_method TEXT,
    price_total INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )
`).run()

// ===== Helpers de análisis (PDF/images) =====
function classifyImageSize(px) {
  if (px >= 1_000_000) return 'large'   // >= 1MP
  if (px >= 300_000)   return 'medium'  // 0.3–1MP
  if (px > 0)          return 'small'
  return 'none'
}

async function getPdfPageCount(pdfPath) {
  const { stdout } = await execFileAsync('pdfinfo', [pdfPath])
  const line = stdout.split('\n').find(l => /^Pages:\s+/i.test(l))
  if (!line) return 1
  const num = parseInt(line.replace(/[^0-9]/g, ''), 10)
  return Number.isFinite(num) ? num : 1
}

async function analyzePdfImages(pdfPath) {
  const { stdout } = await execFileAsync('pdfimages', ['-list', pdfPath])
  const lines = stdout.split('\n').map(s => s.trim()).filter(Boolean)
  let headerIndex = lines.findIndex(l => /^page\b/i.test(l))
  if (headerIndex === -1) {
    headerIndex = lines.findIndex(l => l.toLowerCase().includes('width') && l.toLowerCase().includes('height'))
  }
  const rows = headerIndex >= 0 ? lines.slice(headerIndex + 1) : []

  const images = []
  for (const row of rows) {
    if (!row || /^-+$/.test(row)) continue
    const cols = row.split(/\s+/)
    const page = parseInt(cols[0], 10)
    const width = parseInt(cols[3], 10)
    const height = parseInt(cols[4], 10)
    const color = (cols[5] || '').toLowerCase()
    if (Number.isFinite(page) && Number.isFinite(width) && Number.isFinite(height)) {
      images.push({ page, width, height, color, pixels: width * height })
    }
  }

  const pagesWithImagesSet = new Set(images.map(i => i.page))
  const pagesWithImages = pagesWithImagesSet.size
  const maxPixels = images.reduce((m, i) => Math.max(m, i.pixels), 0)
  const maxImageCategory = classifyImageSize(maxPixels)
  const hasColor = images.some(i => i.color !== 'gray' && i.color !== 'mono' && i.color !== 'indexed-gray')

  const perPageImageCounts = {}
  for (const i of images) perPageImageCounts[i.page] = (perPageImageCounts[i.page] || 0) + 1

  return { images, pagesWithImages, maxPixels, maxImageCategory, hasColor, perPageImageCounts }
}

async function analyzeRasterImage(absPath) {
  const sharp = (await import('sharp')).default
  const meta = await sharp(absPath).metadata()
  const width = meta.width || 0
  const height = meta.height || 0
  const pixels = width * height
  const space = (meta.space || '').toLowerCase() // rgb/gray/cmyk...
  const hasColor = space !== 'b-w' && space !== 'gray' && space !== 'grey'
  return {
    pages: 1,
    pagesWithImages: 1,
    isTextOnly: false,
    hasColor,
    maxPixels: pixels,
    maxImageCategory: classifyImageSize(pixels),
    perPageImageCounts: { 1: 1 }
  }
}

// ===== Rutas =====
app.get('/', (_, res) => res.json({ ok: true, name: 'Impresiones SOS API', version: '1.1.0' }))

// Analizar archivo
app.post('/api/analyze', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'Falta archivo' })

    const file = {
      name: req.file.originalname,
      path: req.file.path,
      storedName: req.file.filename,
      mimeType: req.file.mimetype,
      size: req.file.size,
    }

    let analysis = {
      pages: 1,
      pagesWithImages: 0,
      isTextOnly: true,
      hasColor: false,
      maxPixels: 0,
      maxImageCategory: 'none',
      perPageImageCounts: {}
    }

    if (req.file.mimetype === 'application/pdf') {
      analysis.pages = await getPdfPageCount(file.path)
      try {
        const r = await analyzePdfImages(file.path)
        analysis.pagesWithImages   = r.pagesWithImages
        analysis.hasColor          = r.hasColor
        analysis.maxPixels         = r.maxPixels
        analysis.maxImageCategory  = r.maxImageCategory
        analysis.perPageImageCounts= r.perPageImageCounts
        analysis.isTextOnly        = r.pagesWithImages === 0
      } catch (err) {
        console.warn('pdfimages falló, análisis básico:', err.message)
      }
    } else if (req.file.mimetype.startsWith('image/')) {
      const r = await analyzeRasterImage(file.path)
      analysis = { ...analysis, ...r }
    } else {
      analysis = { ...analysis, pages: 1, isTextOnly: true }
    }

    return res.json({ file, analysis })
  } catch (e) {
    console.error(e)
    return res.status(500).json({ error: 'Error analizando archivo' })
  }
})

// Crear orden (ejemplo básico: guarda los datos que envía el frontend)
app.post('/api/order', (req, res) => {
  try {
    const {
      customer_name, email, phone, address, notes,
      file, params = {}, analysis = {}, price_total = 0
    } = req.body || {}

    const {
      color_mode = 'BN',
      duplex = 'simplex',
      paper_type = 'normal75',
      anillado = 'none',
      photo_size = 'none',
      copies = 1,
      delivery = 'normal',
      desired_date = ''
    } = params

    const normalizedParams = {
      color_mode, duplex, paper_type, anillado, photo_size,
      copies, delivery, desired_date
    }

    const insert = db.prepare(`
      INSERT INTO orders
        (customer_name, email, phone, address, notes,
         file_name, file_mime, file_size,
         params_json, desired_date, payment_method, price_total)
      VALUES
        (@customer_name, @email, @phone, @address, @notes,
         @file_name, @file_mime, @file_size,
         @params_json, @desired_date, @payment_method, @price_total)
    `)

    const result = insert.run({
      customer_name: customer_name || '',
      email: email || '',
      phone: phone || '',
      address: address || '',
      notes: notes || '',
      file_name: file?.name || '',
      file_mime: file?.mimeType || '',
      file_size: Number(file?.size) || 0,
      params_json: JSON.stringify(normalizedParams),
      desired_date: desired_date || null,
      payment_method: 'transferencia',
      price_total: Number(price_total) || 0
    })

    res.json({ order_id: result.lastInsertRowid, total: Number(price_total) || 0 })
  } catch (e) {
    console.error(e)
    res.status(500).json({ error: 'No se pudo crear la orden' })
  }
})

// Listado para admin (simple)
app.get('/api/orders', (req, res) => {
  try {
    const rows = db.prepare(`
      SELECT id, created_at, customer_name, email, phone, address,
             price_total, desired_date, payment_method
      FROM orders ORDER BY id DESC LIMIT 200
    `).all()
    res.json(rows)
  } catch (e) {
    console.error(e)
    res.status(500).json({ error: 'No se pudo listar órdenes' })
  }
})

app.listen(PORT, () => {
  console.log(`Impresiones SOS server escuchando en http://localhost:${PORT}`)
})
