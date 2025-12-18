FROM node:18-alpine

WORKDIR /app

COPY package*.json ./

RUN npm install --production

COPY . .

EXPOSE 8080

ENV PORT=8080
ENV DEBUG_MODE=false
ENV USE_API_KEY=false
ENV MAX_WORKERS=3

CMD ["node", "proxy-server.js"]
