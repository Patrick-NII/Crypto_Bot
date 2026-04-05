# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app

# Version + environment injected at build time
ARG APP_VERSION=0.0.0-dev
ARG APP_ENV=development
ARG BUILD_SHA=unknown
ENV NEXT_PUBLIC_APP_VERSION=${APP_VERSION}
ENV NEXT_PUBLIC_APP_ENV=${APP_ENV}
ENV NEXT_PUBLIC_BUILD_SHA=${BUILD_SHA}

COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine
COPY --from=builder /app/out /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
