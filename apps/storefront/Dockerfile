FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npx tsc --noEmit && mkdir -p /app/dist && cp index.html /app/dist/index.html && cp -r public/* /app/dist/

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1:80/ >/dev/null || exit 1
CMD ["nginx", "-g", "daemon off;"]
