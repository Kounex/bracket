# Build static files
FROM node:25-alpine AS builder

WORKDIR /app

ENV NODE_ENV=production

COPY . .

RUN apk add pnpm && \
    CI=true pnpm install && \
    pnpm build

# Production image, copy all the static files and run next
FROM caddy:2-alpine AS runner

WORKDIR /app

COPY --from=builder /app/dist /app/dist
COPY --from=builder /app/Caddyfile /etc/caddy/Caddyfile
COPY --from=builder /app/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 3000

HEALTHCHECK --interval=3s --timeout=5s --retries=10 \
    CMD ["wget", "-O", "/dev/null", "http://localhost:3000"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
