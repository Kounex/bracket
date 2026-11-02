# Build static files
FROM node:25.9.0-alpine@sha256:bdf2cca6fe3dabd014ea60163eca3f0f7015fbd5c7ee1b0e9ccb4ced6eb02ef4 AS builder

WORKDIR /app

ENV NODE_ENV=production

COPY . .

RUN apk add pnpm && \
    CI=true pnpm install && \
    pnpm build

# Production image, copy all the static files and run next
FROM caddy:2.11.7-alpine@sha256:e70b164da81ef698b3ad19af799ea6086ce6d9e48ed4079eb9fe26f6fbf14ee5 AS runner

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
