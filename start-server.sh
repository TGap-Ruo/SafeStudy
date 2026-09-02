#!/usr/bin/env bash
# =============================================================
# WeBan Web 启动/停止/重启脚本（部署后日常维护、服务器重启后使用）
# -------------------------------------------------------------
# 优先使用 systemd 服务（deploy.sh 已注册 weban-web 与
# weban-cdp-chrome）；若 systemd 不可用（如未注册/容器内），
# 自动回退到 nohup 后台方式。
#
# 用法（需 root）：
#   sudo ./start-server.sh             # 同 start
#   sudo ./start-server.sh start       # 启动 Chrome CDP + Web 服务
#   sudo ./start-server.sh stop        # 停止全部
#   sudo ./start-server.sh restart     # 重启全部
#   sudo ./start-server.sh status      # 查看状态
# =============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-5000}"
CDP_HOST="${WEBBAN_CDP_HOST:-127.0.0.1}"
CDP_PORT="${WEBBAN_CDP_PORT:-9222}"

WEB_UNIT="weban-web.service"
CDP_UNIT="weban-cdp-chrome.service"

GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; NC=$'\033[0m'
info() { echo -e "${GREEN}[信息]${NC} $*"; }
warn() { echo -e "${YELLOW}[警告]${NC} $*"; }
err()  { echo -e "${RED}[错误]${NC} $*"; }

have_systemd() {
    command -v systemctl >/dev/null 2>&1 \
        && [ -f "/etc/systemd/system/$WEB_UNIT" ] \
        && [ -f "$ROOT/cdp-chrome.sh" ]
}

web_health() {
    curl -fsS --max-time 3 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1
}

cdp_health() {
    (exec 3<>"/dev/tcp/$CDP_HOST/$CDP_PORT") 2>/dev/null
}

action_systemd() {
    local act="$1"
    case "$act" in
        start)
            systemctl enable --now "$CDP_UNIT" >/dev/null 2>&1 || true
            systemctl enable --now "$WEB_UNIT"
            ;;
        stop)
            systemctl stop "$WEB_UNIT" 2>/dev/null || true
            systemctl stop "$CDP_UNIT" 2>/dev/null || true
            ;;
        restart)
            systemctl restart "$WEB_UNIT"
            systemctl restart "$CDP_UNIT" 2>/dev/null || true
            ;;
    esac
    sleep 2
    show_status
}

# ── nohup 回退模式（无 systemd 时）─────────────────────────
WEB_PID_FILE="$ROOT/logs/web.pid"
WEB_LOG_FILE="$ROOT/logs/web.log"
PYTHON="$ROOT/venv/bin/python3"

fallback_status() {
    local web_pid=""
    [ -f "$WEB_PID_FILE" ] && web_pid="$(cat "$WEB_PID_FILE" 2>/dev/null || true)"
    if [ -n "$web_pid" ] && kill -0 "$web_pid" 2>/dev/null; then
        info "Web 服务运行中 (PID $web_pid): http://0.0.0.0:$PORT"
    else
        warn "Web 服务未运行"
    fi
    if [ -x "$ROOT/cdp-chrome.sh" ]; then
        "$ROOT/cdp-chrome.sh" status || true
    fi
}

action_fallback() {
    local act="$1"
    case "$act" in
        start)
            mkdir -p "$ROOT/logs"
            if [ -x "$ROOT/cdp-chrome.sh" ]; then
                "$ROOT/cdp-chrome.sh" start
            fi
            if [ ! -x "$PYTHON" ]; then
                err "未找到 $PYTHON，请先运行 deploy.sh 完成部署"
                exit 1
            fi
            local old_pid=""
            [ -f "$WEB_PID_FILE" ] && old_pid="$(cat "$WEB_PID_FILE" 2>/dev/null || true)"
            if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
                info "Web 服务已在运行 (PID $old_pid)"
            else
                cd "$ROOT"
                nohup "$PYTHON" app.py >>"$WEB_LOG_FILE" 2>&1 &
                echo $! >"$WEB_PID_FILE"
                info "Web 服务已启动 (PID $(cat "$WEB_PID_FILE"))，日志: logs/web.log"
            fi
            sleep 2
            ;;
        stop)
            local old_pid=""
            [ -f "$WEB_PID_FILE" ] && old_pid="$(cat "$WEB_PID_FILE" 2>/dev/null || true)"
            if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
                kill "$old_pid" 2>/dev/null || true
                info "Web 服务已停止 (PID $old_pid)"
            fi
            if [ -x "$ROOT/cdp-chrome.sh" ]; then
                "$ROOT/cdp-chrome.sh" stop
            fi
            ;;
        restart)
            action_fallback stop
            action_fallback start
            return
            ;;
    esac
    show_status
}

show_status() {
    echo
    if have_systemd; then
        systemctl is-active "$WEB_UNIT" >/dev/null 2>&1 \
            && info "Web 服务: 运行中 (systemd: $WEB_UNIT)" \
            || warn "Web 服务: 未运行"
        systemctl is-active "$CDP_UNIT" >/dev/null 2>&1 \
            && info "Chrome CDP: 运行中 (systemd: $CDP_UNIT)" \
            || warn "Chrome CDP: 未运行"
    else
        fallback_status
    fi
    echo
    web_health && info "健康检查通过: http://127.0.0.1:$PORT/api/health"
    cdp_health && info "Chrome CDP 正常: http://$CDP_HOST:$CDP_PORT"
    echo
    info "Web 管理页面: http://服务器IP:$PORT"
    info "日志: journalctl -u weban-web -f"
}

ACT="${1:-start}"
case "$ACT" in
    start|stop|restart)
        if [ "$(id -u)" -ne 0 ]; then
            err "请以 root 运行：sudo ./start-server.sh $ACT"
            exit 1
        fi
        if have_systemd; then
            action_systemd "$ACT"
        else
            action_fallback "$ACT"
        fi
        ;;
    status)
        show_status
        ;;
    *)
        awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print } NR > 1 && !/^#/ { exit }' "$0"
        exit 1
        ;;
esac
