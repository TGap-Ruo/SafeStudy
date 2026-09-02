#!/usr/bin/env bash
# =============================================================
# WeBan Web（SafeStudy）Ubuntu 一键部署脚本
# -------------------------------------------------------------
# 适用系统：Ubuntu 20.04+ / Debian 11+（x86_64，需 GLIBC 2.38+ 则建议 Ubuntu 24.04）
# 部署方式：以 root 运行，Web 服务 + Chrome CDP(--no-sandbox) 两个 systemd 服务
#
# 用法：
#   sudo bash deploy.sh
#     默认从 Gitee 镜像仓库下载代码并完成部署；重复执行 = 更新项目
#     国内服务器推荐 Gitee；如需走 GitHub：
#       GIT_HOST=github REPO=TGap-Ruo/SafeStudy sudo -E bash deploy.sh
#
# 可选环境变量：
#   GIT_HOST  代码源，默认 gitee（可选 github）
#   REPO      仓库地址，默认 tgap/safe-study
#   BRANCH    分支，默认 main
#   APP_DIR   安装目录，默认 /www/wwwroot/weban-web（会保留已有 logs/tasks.json）
#   PIP_INDEX  pip 镜像源，默认清华 PyPI（国内服务器必用）
#   SKIP_INSTALL=1  跳过系统依赖/Chrome 安装，只更新代码并重启服务
# =============================================================
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

REPO="${REPO:-tgap/safe-study}"
GIT_HOST="${GIT_HOST:-gitee}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/www/wwwroot/weban-web}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"
PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"

GREEN=$'\033[32m'; RED=$'\033[31m'; YELLOW=$'\033[33m'; NC=$'\033[0m'
info()  { echo -e "${GREEN}[信息]${NC} $*"; }
warn()  { echo -e "${YELLOW}[警告]${NC} $*"; }
err()   { echo -e "${RED}[错误]${NC} $*"; }

TMP_ROOT="$(mktemp -d /tmp/safestudy-deploy.XXXXXX)"
cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT

# ── 0. 前置检查 ──────────────────────────────────────────────
if [ "$(id -u)" -ne 0 ]; then
    err "请以 root 运行：sudo bash deploy.sh"
    exit 1
fi
if [ "$(uname -m)" != "x86_64" ]; then
    warn "当前架构 $(uname -m)，WeBan 二进制为 x86_64，可能无法运行"
fi

info "目标目录: $APP_DIR"
info "源码仓库: $REPO ($BRANCH)"

# ── 1. 系统依赖 + Chrome ─────────────────────────────────────
install_system_deps() {
    info "安装系统依赖..."
    apt-get update -y -q
    apt-get install -y -q \
        python3 python3-venv python3-pip \
        wget unzip curl rsync ca-certificates

    if command -v google-chrome-stable >/dev/null 2>&1; then
        info "Google Chrome 已安装：$(google-chrome-stable --version)"
    else
        info "安装 Google Chrome（WeBan 浏览器必需）..."
        local deb="$TMP_ROOT/google-chrome-stable_current_amd64.deb"
        wget -q --timeout=120 -O "$deb" \
            https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
        apt-get install -y "$deb" || apt-get -f install -y
        google-chrome-stable --version
    fi
}

[ "$SKIP_INSTALL" = "1" ] || install_system_deps

# ── 2. 下载源码（默认 Gitee，可用 GIT_HOST=github 切回 GitHub） ──
SRC_DIR="$TMP_ROOT/src"
mkdir -p "$SRC_DIR"

case "$GIT_HOST" in
    github) DOWNLOAD_URL="https://github.com/$REPO/archive/refs/heads/$BRANCH.zip" ;;
    gitee)  DOWNLOAD_URL="https://gitee.com/$REPO/repository/archive/$BRANCH.zip" ;;
    *) err "不支持的 GIT_HOST: $GIT_HOST（可选 gitee / github）"; exit 1 ;;
esac

info "从 $GIT_HOST 下载源码: $DOWNLOAD_URL"
if ! wget -q --timeout=120 -O "$SRC_DIR/repo.zip" "$DOWNLOAD_URL" \
    || ! unzip -q -o "$SRC_DIR/repo.zip" -d "$SRC_DIR"; then
    err "下载失败：请确认仓库 $REPO 为公开、分支 $BRANCH 存在，且服务器可访问 $GIT_HOST"
    exit 1
fi
info "源码下载成功"

# 定位项目根目录（兼容 zip 外层多一级目录，如 SafeStudy-main/）
PROJECT_ROOT=""
if [ -f "$SRC_DIR/app.py" ] && [ -f "$SRC_DIR/task_manager.py" ]; then
    PROJECT_ROOT="$SRC_DIR/"
else
    for d in "$SRC_DIR"/*/; do
        if [ -f "$d/app.py" ] && [ -f "$d/task_manager.py" ]; then
            PROJECT_ROOT="$d"
            break
        fi
    done
fi
if [ -z "$PROJECT_ROOT" ]; then
    err "源码中未找到 app.py + task_manager.py，仓库结构与预期不符"
    err "请确认上传的是 weban-web 项目本体，而不是其它目录"
    exit 1
fi
[ -f "$PROJECT_ROOT/requirements.txt" ] || {
    err "源码缺少 requirements.txt"; exit 1; }

# ── 3. 部署到目标目录（保留已有 logs/tasks.json/venv） ──────
mkdir -p "$APP_DIR"
info "同步代码到 $APP_DIR ..."
rsync -a \
    --exclude 'logs/' \
    --exclude 'tasks.json' \
    --exclude 'venv/' \
    --exclude '.git/' \
    --exclude '__pycache__/' \
    "$PROJECT_ROOT" "$APP_DIR/"

chmod +x "$APP_DIR/cdp-chrome.sh" 2>/dev/null || true
chmod +x "$APP_DIR/programs/weban/WeBan-linux-x64" 2>/dev/null || true
if [ ! -f "$APP_DIR/programs/weban/WeBan-linux-x64" ] \
   && [ ! -f "$APP_DIR/programs/safety/main.py" ]; then
    warn "未检测到可执行程序（programs/weban/WeBan-linux-x64），任务将无法运行"
fi

# ── 4. Python 虚拟环境 ───────────────────────────────────────
if [ ! -x "$APP_DIR/venv/bin/python3" ]; then
    info "创建 Python 虚拟环境..."
    python3 -m venv "$APP_DIR/venv"
fi
info "安装 Python 依赖..."
"$APP_DIR/venv/bin/pip" install -q --upgrade pip -i "$PIP_INDEX"
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt" -i "$PIP_INDEX"

# ── 5. systemd 服务：Chrome CDP + Web 服务 ──────────────────
if [ -f "$APP_DIR/cdp-chrome.sh" ]; then
    info "写入服务 /etc/systemd/system/weban-cdp-chrome.service ..."
    cat > /etc/systemd/system/weban-cdp-chrome.service <<EOF
[Unit]
Description=WeBan CDP Chrome (no-sandbox)
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/cdp-chrome.sh start
ExecStop=$APP_DIR/cdp-chrome.sh stop

[Install]
WantedBy=multi-user.target
EOF
else
    warn "未找到 cdp-chrome.sh，跳过 CDP Chrome 服务（仅安装 Web 服务）"
fi

info "写入服务 /etc/systemd/system/weban-web.service ..."
cat > /etc/systemd/system/weban-web.service <<EOF
[Unit]
Description=WeBan Web Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python3 app.py
Restart=always
RestartSec=5
Environment="PYTHONUNBUFFERED=1"
Environment="PATH=$APP_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="WEBBAN_CDP_HOST=127.0.0.1"
Environment="WEBBAN_CDP_PORT=9222"

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
if [ -f "$APP_DIR/cdp-chrome.sh" ]; then
    systemctl enable --now weban-cdp-chrome
fi
systemctl enable --now weban-web

# ── 6. 防火墙 ────────────────────────────────────────────────
if command -v ufw >/dev/null 2>&1; then
    ufw allow 5000/tcp >/dev/null 2>&1 || true
    info "防火墙已放行 5000/tcp（9222 仅本机监听，未对外开放）"
fi

# ── 7. 健康检查与提示 ────────────────────────────────────────
sleep 2
cd "$APP_DIR"

echo
info "服务状态："
systemctl is-active weban-cdp-chrome >/dev/null 2>&1 \
    && info "  weban-cdp-chrome  运行中" \
    || warn "  weban-cdp-chrome  未运行"
systemctl is-active weban-web >/dev/null 2>&1 \
    && info "  weban-web          运行中" \
    || err "  weban-web          未运行（见下方日志）"

if command -v curl >/dev/null 2>&1; then
    if curl -fsS --max-time 3 http://127.0.0.1:9222/json/version >/dev/null 2>&1; then
        info "Chrome CDP 正常: http://127.0.0.1:9222"
    else
        warn "Chrome CDP 未就绪，请查看: journalctl -u weban-cdp-chrome"
    fi
    if curl -fsS --max-time 3 http://127.0.0.1:5000/api/health >/dev/null 2>&1; then
        info "Web 服务正常: http://127.0.0.1:5000/api/health"
    fi
fi

echo
info "部署完成！访问: http://服务器IP:5000"
info "查看日志: journalctl -u weban-web -f"
info "重新部署: 再次运行本脚本即可（自动覆盖代码并重启，保留日志数据）"
