#!/usr/bin/env bash
# ============================================================
# MemoLoop 评审期可用性自检（由 cron 每分钟调用）
#   curl http://localhost/api/health 失败 → 重启 backend 并刷新 nginx DNS 缓存
# 安装（root 执行一次）:
#   echo '* * * * * root bash /opt/memoloop/deploy/selfcheck.sh >> /var/log/memoloop-selfcheck.log 2>&1' \
#     > /etc/cron.d/memoloop-selfcheck
# ============================================================
set -uo pipefail

cd "$(dirname "$0")/.."   # 项目根目录
COMPOSE="docker compose -f docker-compose.prod.yml"

# 走 nginx 入口完整链路：nginx → backend → postgres
if curl -fsS --max-time 10 http://localhost/api/health >/dev/null 2>&1; then
  exit 0
fi

echo "[$(date '+%F %T')] 健康检查失败，尝试恢复…"

# 1) 容器状态对齐（任何挂掉的容器拉起来）
$COMPOSE up -d >/dev/null 2>&1

# 2) 若仍失败：单独重启 backend（最常见故障点：LLM 请求堆积 / worker 挂起）
if ! curl -fsS --max-time 10 http://localhost/api/health >/dev/null 2>&1; then
  echo "[$(date '+%F %T')] 重启 backend"
  $COMPOSE restart backend
fi

# 3) backend 重启后 IP 可能变化，刷新 nginx 的 Docker DNS 解析
$COMPOSE exec -T frontend nginx -s reload >/dev/null 2>&1 || true

# 4) 仍失败则整个栈重启（兜底，正常情况下走不到这里）
if ! curl -fsS --max-time 15 http://localhost/api/health >/dev/null 2>&1; then
  echo "[$(date '+%F %T')] 全栈重启兜底"
  $COMPOSE restart
fi

echo "[$(date '+%F %T')] 恢复动作结束"
