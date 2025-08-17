FROM node:20-bullseye

# Dependencias del sistema para PDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY . .

RUN mkdir -p /app/uploads

# Render inyecta PORT pero exponemos uno por defecto
ENV PORT=10000
EXPOSE 10000

CMD ["node", "index.js"]
