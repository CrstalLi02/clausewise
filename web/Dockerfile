# Clausewise frontend (Next.js)
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:24-alpine AS build
WORKDIR /app
# BACKEND_URL is read at build time in next.config.mjs and must be injected as a build arg
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=$BACKEND_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
