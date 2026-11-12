#!/usr/bin/env bash
# ============================================================
# MemoLoop 生产环境一键初始化（在服务器项目根目录执行）
#   bash deploy/init.sh
# 幂等，可重复执行。做四件事：
#   1. 由 .env 自动生成生产配置 .env.prod（改数据库地址/CORS）
#   2. docker compose 构建并启动 postgres + backend + frontend
#   3. 等待后端健康检查通过
#   4. 建演示账号 + 导入预置课件并建卡（真实 LLM 调用，1~3 分钟）
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."   # 项目根目录
COMPOSE="docker compose -f docker-compose.prod.yml"

echo "==> [0/4] 前置检查"
command -v docker >/dev/null || { echo "错误: 未安装 docker"; exit 1; }
$COMPOSE version >/dev/null 2>&1 || { echo "错误: docker compose 插件不可用"; exit 1; }
[ -f .env ] || { echo "错误: 项目根目录缺少 .env（含硅基流动密钥）"; exit 1; }

echo "==> [1/4] 生成 .env.prod"
if [ ! -f .env.prod ]; then
  # 数据库地址指向 compose 内网 postgres；CORS 加上本机公网 IP（有域名时手动补充）
  PUB_IP=$(curl -fsS --max-time 5 ifconfig.me 2>/dev/null || echo "")
  CORS_EXTRA=""
  [ -n "$PUB_IP" ] && CORS_EXTRA="http://${PUB_IP}"
  sed -e 's#^DATABASE_URL=.*#DATABASE_URL=postgresql+asyncpg://memoloop:memoloop_prod_pwd@postgres:5432/memoloop#' \
      -e "s#^CORS_ORIGINS=.*#CORS_ORIGINS=http://${PUB_IP:-localhost}${CORS_EXTRA:+,$CORS_EXTRA},http://localhost#" \
      .env > .env.prod
  echo "    已生成 .env.prod（公网 IP: ${PUB_IP:-未知，稍后手动改 CORS_ORIGINS}）"
else
  echo "    .env.prod 已存在，跳过"
fi

echo "==> [2/4] 构建并启动（前端首次构建约 3~5 分钟）"
$COMPOSE up -d --build

echo "==> [3/4] 等待后端健康检查"
for i in $(seq 1 60); do
  if $COMPOSE exec -T backend python -c \
       "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health',timeout=5).status==200 else 1)" \
       >/dev/null 2>&1; then
    echo "    后端已就绪 (等待 ${i}0 秒)"; break
  fi
  [ "$i" = "60" ] && { echo "错误: 后端 10 分钟未就绪，查看日志:"; $COMPOSE logs --tail 50 backend; exit 1; }
  sleep 10
done

echo "==> [4/4] 预置演示数据（账号 + 课件建卡，真实 LLM 调用）"
$COMPOSE exec -T backend python -m scripts.seed_demo
$COMPOSE exec -T backend python -m scripts.seed_demo_data

echo ""
echo "=========================================="
echo " 初始化完成！"
echo " 访问:      http://$(curl -fsS --max-time 5 ifconfig.me 2>/dev/null || echo '<服务器IP>')"
echo " 演示账号:  demo@memoloop.cn / Demo@2026"
echo " 常用命令:"
echo "   看日志:   $COMPOSE logs -f backend"
echo "   重启:     $COMPOSE restart"
echo "   停止:     $COMPOSE down（数据卷保留）"
echo "=========================================="
