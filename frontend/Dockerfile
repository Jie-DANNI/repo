# ---------- 阶段 1：构建前端静态资源 ----------
FROM node:22-alpine AS build
WORKDIR /app

# 国内镜像加速（构建机在国内时明显提速，海外亦可用）
RUN npm config set registry https://registry.npmmirror.com

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ---------- 阶段 2：nginx 托管静态资源 + 反代后端 ----------
FROM nginx:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
