FROM node:20-alpine
WORKDIR /app
COPY binance-proxy.mjs .
EXPOSE 3001
CMD ["node", "binance-proxy.mjs"]
