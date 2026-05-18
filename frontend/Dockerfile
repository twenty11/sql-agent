# ==================== Frontend Dockerfile - 生产环境 ====================

# 第一阶段：构建 React 应用
FROM node:20-alpine AS builder
WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmjs.org/

COPY frontend/package*.json ./
RUN npm ci --registry=${NPM_REGISTRY} --replace-registry-host=always

COPY frontend/ ./
RUN npm run build

# 第二阶段：使用 Nginx 提供静态文件
FROM nginx:1.28-alpine

# 复制前端构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制优化后的 Nginx 配置
COPY nginx.prod.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
