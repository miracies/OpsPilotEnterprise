FROM node:20-slim AS builder
WORKDIR /app
COPY apps/web/package.json apps/web/pnpm-lock.yaml* ./
RUN corepack enable && pnpm install --frozen-lockfile 2>/dev/null || pnpm install
COPY apps/web/ .
COPY packages/shared-types/ /packages/shared-types/
RUN pnpm build

FROM node:20-slim
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
