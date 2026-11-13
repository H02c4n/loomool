FROM node:24.22.0-alpine

RUN npm install -g pnpm@10

WORKDIR /app

COPY package.json ./
RUN pnpm install --no-frozen-lockfile

COPY . .

EXPOSE 3001
CMD ["pnpm", "dev", "--port", "3001"]
