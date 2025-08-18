FROM node:20-bullseye

# Dependencias del sistema para PDF (pdfinfo, pdfimages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiamos primero package.json / lock para cache de npm ci
COPY package*.json ./
RUN npm ci --omit=dev

# Copiamos el resto del código
COPY . .

# Carpetas de trabajo (uploads y DB en /app)
RUN mkdir -p /app/uploads

# Render inyecta PORT; exponemos 10000 por consistencia
ENV PORT=10000
EXPOSE 10000

CMD ["node", "index.js"]
