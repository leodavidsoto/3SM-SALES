FROM node:20-bullseye

# Dependencias del sistema para PDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia package.json / package-lock.json primero para cache
COPY package*.json ./
# Si usas "type": "module" en package.json, Node 20 ya soporta ESM
RUN npm ci --omit=dev

# Copia el resto del código
COPY . .

# Crea carpeta de uploads (efímera en free)
RUN mkdir -p /app/uploads

# Render asigna el puerto por la variable $PORT
ENV PORT=10000
EXPOSE 10000

CMD ["node", "index.js"]
