#!/usr/bin/env bash
# 以 CDP 模式启动一个带 --no-sandbox 的 Chrome，供 WeBan 任务连接。
#
# 适用场景：Web 服务以 root 运行（宝塔面板 / systemd User=root）或运行在
# 容器内。此时 nodriver 直接启动 Chrome 会因沙箱不可用而失败
# （"Failed to connect to browser ... pass no_sandbox=True"），
# 需要先用本脚本启动 Chrome，再给服务设置 WEBBAN_CDP_HOST/WEBBAN_CDP_PORT
# 让任务通过 CDP 连接，不再自己拉起浏览器。
#
# 用法:
#   ./cdp-chrome.sh start    后台启动（默认 127.0.0.1:9222）
#   ./cdp-chrome.sh stop     停止
#   ./cdp-chrome.sh status   查看状态
#   ./cdp-chrome.sh run      前台运行（调试用，Ctrl+C 结束）
#
# 环境变量:
#   WEBBAN_CHROME_PATH         Chrome 可执行文件路径（默认 /usr/bin/google-chrome-stable）
#   WEBBAN_CDP_HOST            监听地址（默认 127.0.0.1；公网需配合防火墙）
#   WEBBAN_CDP_PORT            调试端口（默认 9222）
#   WEBBAN_CDP_USER_DATA_DIR   Chrome 用户数据目录（默认 logs/.chrome-cdp）
#   WEBBAN_CDP_LOG             日志文件（默认 logs/chrome-cdp.log）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
CHROME_PATH="${WEBBAN_CHROME_PATH:-/usr/bin/google-chrome-stable}"
CDP_HOST="${WEBBAN_CDP_HOST:-127.0.0.1}"
CDP_PORT="${WEBBAN_CDP_PORT:-9222}"
DATA_DIR="${WEBBAN_CDP_USER_DATA_DIR:-$ROOT/logs/.chrome-cdp}"
LOG_FILE="${WEBBAN_CDP_LOG:-$ROOT/logs/chrome-cdp.log}"
PID_FILE="${WEBBAN_CDP_PID_FILE:-$ROOT/logs/chrome-cdp.pid}"

mkdir -p "$DATA_DIR" "$(dirname "$LOG_FILE")"

CMD=(
    "$CHROME_PATH"
    --headless=new
    --no-sandbox
    --disable-gpu
    --disable-dev-shm-usage
    --no-first-run
    --no-default-browser-check
    --mute-audio
    "--remote-debugging-address=$CDP_HOST"
    "--remote-debugging-port=$CDP_PORT"
    "--user-data-dir=$DATA_DIR"
)

require_chrome() {
    if [ ! -x "$CHROME_PATH" ]; then
        echo "[错误] 未找到 Chrome: $CHROME_PATH" >&2
        echo "[错误] 请安装 Google Chrome，或用 WEBBAN_CHROME_PATH 指定路径" >&2
        exit 1
    fi
}

pid_of() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    fi
}

is_running() {
    local pid
    pid="$(pid_of)"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

cdp_up() {
    # 仅检查端口可连（不依赖 curl）；Chrome 就绪后会开始监听该端口
    (exec 3<>"/dev/tcp/$CDP_HOST/$CDP_PORT") 2>/dev/null
}

wait_ready() {
    local i
    for i in $(seq 1 60); do
        if cdp_up; then
            return 0
        fi
        sleep 0.5
    done
    return 1
}

case "${1:-}" in
    start)
        require_chrome
        if is_running; then
            echo "Chrome CDP 已在运行 (PID $(pid_of)): http://$CDP_HOST:$CDP_PORT"
            exit 0
        fi
        nohup "${CMD[@]}" >"$LOG_FILE" 2>&1 &
        echo $! >"$PID_FILE"
        if wait_ready; then
            echo "Chrome CDP 已就绪 (PID $(pid_of)): http://$CDP_HOST:$CDP_PORT"
        else
            echo "[错误] Chrome 启动失败，请查看日志: $LOG_FILE" >&2
            exit 1
        fi
        ;;
    stop)
        if is_running; then
            kill "$(pid_of)" 2>/dev/null || true
            rm -f "$PID_FILE"
            echo "Chrome CDP 已停止"
        else
            echo "Chrome CDP 未在运行"
            rm -f "$PID_FILE"
        fi
        ;;
    status)
        if is_running; then
            echo "运行中 (PID $(pid_of)): http://$CDP_HOST:$CDP_PORT"
            if cdp_up; then
                echo "CDP 接口正常"
            else
                echo "CDP 接口不可达（进程可能已僵死）"
            fi
        else
            echo "未运行"
            exit 1
        fi
        ;;
    run)
        require_chrome
        exec "${CMD[@]}"
        ;;
    *)
        awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print } NR > 1 && !/^#/ { exit }' "$0"
        exit 1
        ;;
esac
