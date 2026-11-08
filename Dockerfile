# App and routing cache for Cloud Run (Z-4: project <gcp-project>, region us-east1).
# The Build (data preparation) runs before this image build and writes its output under public/.

FROM node:26-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN ORS_API_KEY='' npm run build

FROM node:26-alpine
RUN apk add --no-cache nginx
WORKDIR /app
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY scripts/cache-drive-times.ts ./scripts/cache-drive-times.ts
COPY src/map/driveTimes.ts src/map/proximity.ts ./src/map/
RUN ln -s /usr/share/nginx/html public
EXPOSE 8080
CMD ["sh", "-c", "node scripts/cache-drive-times.ts --watch & exec nginx -g 'daemon off;'"]
