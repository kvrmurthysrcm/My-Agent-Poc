FROM node:24.10-alpine AS dependencies
WORKDIR /app
COPY modules/angular-ui/package.json modules/angular-ui/package-lock.json ./
RUN npm ci

FROM dependencies AS test
COPY modules/angular-ui/ ./
RUN npm test -- --watch=false

FROM dependencies AS build
COPY modules/angular-ui/ ./
RUN npm run build

FROM nginx:1.29-alpine AS runtime
COPY modules/angular-ui/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/rag-agent-angular-ui/browser /usr/share/nginx/html
EXPOSE 8080

