FROM node:22-bookworm-slim

WORKDIR /app

COPY web-ui/package.json web-ui/package-lock.json ./
RUN npm install

COPY web-ui ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

