#!/bin/bash
# 自动化任务管理平台 - 启动脚本
# 用法: ./start.sh [端口号]  默认端口 5000
# WeBan 使用编译好的二进制可执行文件，无需安装 Python 依赖
# 浏览器使用系统安装的 Google Chrome

cd "$(dirname "$0")"

PORT=${1:-5000}
VENV_DIR="venv"
CHROME_PATH="${WEBBAN_CHROME_PATH:-/usr/bin/google-chrome-stable}"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

# 检查 Google Chrome（WeBan 运行必需）
if [ ! -f "$CHROME_PATH" ]; then
    echo "[警告] 未检测到 Google Chrome（$CHROME_PATH）"
    echo "[警告] WeBan 程序将无法运行，请先安装："
    echo "  wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
    echo "  dpkg -i google-chrome-stable_current_amd64.deb"
    echo "  apt -f install -y"
    echo ""
fi

# root 用户提示：Chrome 沙箱不允许 root，需配置 CDP 模式或用非 root 用户运行
if [ "$(id -u)" = "0" ]; then
    if [ -z "${WEBBAN_CDP_HOST:-}" ] || [ -z "${WEBBAN_CDP_PORT:-}" ]; then
        echo "[警告] 当前以 root 运行，且未配置 WEBBAN_CDP_HOST / WEBBAN_CDP_PORT"
        echo "[警告] WeBan 任务会报 'Failed to connect to browser ... pass no_sandbox=True'"
        echo "[警告] 请先执行 ./cdp-chrome.sh start，并设置上述环境变量（见 DEPLOY.md 4.4），"
        echo "[警告] 或改用非 root 用户运行本服务"
        echo ""
    fi
fi

# 创建虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "[信息] 创建 Python 虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 安装依赖
echo "[信息] 检查并安装依赖..."
python3 -m pip install -q --upgrade pip
python3 -m pip install -q -r requirements.txt

echo "[信息] 启动服务，端口: $PORT"
echo "[信息] 访问地址: http://0.0.0.0:$PORT"
echo "[信息] 按 Ctrl+C 停止"

# 启动 Flask
exec python3 app.py
