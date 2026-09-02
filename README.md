# SafeStudy · 自动化任务管理平台（WeBan Web）

一个部署在 Linux 云服务器上的 **安全教育平台自动完成任务的 Web 管理端**：在网页上填写学校、账号、密码即可一键运行，支持后台多开、实时终端输出、日志下载与任务管理。

平台内置两种自动化程序：

| 程序 | 说明 |
|------|------|
| **WeBan 安全微伴** | 通过编译版二进制（nodriver 驱动 Chrome）自动完成安全教育平台的学习与考试任务，内置题库、验证码识别与 AI 搜题 |
| **江苏安全平台** | 通过数据包重放完成课程学习（Python + requests），内置题库 |

> ⚠️ **使用声明**：本项目仅用于学习与技术交流。请遵守所在学校/平台的使用规则，账号风险自负，请勿滥用。

---

## 功能特性

- 🌐 网页一键启动：选择程序类型，填写学校 / 账号 / 密码即可运行
- 🧵 后台多开：多个账号独立进程并行运行，互不干扰
- 📺 实时终端输出（SSE 推送），可自动滚动、一键清空
- 📥 运行日志持久化并可下载（每个任务独立目录）
- 🛑 任务管理：运行状态、停止、删除
- 📊 任务统计：运行中 / 已完成 / 失败 数量一目了然
- 🔁 systemd 常驻 + 开机自启，崩溃自动重启
- 🚀 从 GitHub 公开仓库云端一键部署，一条命令完成

---

## 项目结构

```text
.
├── app.py                  # Flask 主应用（页面 + API + SSE）
├── task_manager.py         # 任务管理器（子进程、输出缓冲、日志持久化）
├── deploy.sh               # Ubuntu 云端一键部署脚本（推荐）
├── start-server.sh         # 日常启停 / 重启 / 状态脚本
├── cdp-chrome.sh           # root 环境下以 --no-sandbox 启动 Chrome CDP
├── start.sh                # 手动命令行启动脚本（备用）
├── requirements.txt        # Web 服务依赖（仅 flask + requests）
├── templates/index.html    # 网页前端（单页应用）
├── programs/
│   ├── weban/              # WeBan 安全微伴（二进制 + 题库 + 验证码模型）
│   │   ├── WeBan-linux-x64
│   │   ├── answer/answer.json
│   │   └── captcha_model.onnx
│   └── safety/             # 江苏安全平台（Python 脚本）
├── logs/                   # 运行后生成：任务日志、Chrome CDP 日志
├── tasks.json              # 运行后生成：任务记录
└── DEPLOY.md               # 详细部署与运维手册
```

---

## 服务器要求

| 项目 | 要求 |
|------|------|
| 操作系统 | **Ubuntu 20.04+ / Debian 11+**（WeBan 二进制需要 GLIBC 2.38+，建议 **Ubuntu 24.04**） |
| 架构 | **x86_64**（ARM 需替换 arm64 版二进制，见 FAQ） |
| Python | 3.8+（仅 Web 服务使用，脚本自动安装） |
| 内存 | 最低 1GB；多开建议 2GB+（WeBan 每实例约 200-400MB） |
| 浏览器 | 脚本自动安装 Google Chrome（WeBan 必需） |

> 宝塔面板（/www/wwwroot）或任意 root 权限的云服务器均可，脚本默认安装到 `/www/wwwroot/weban-web`。

---

## 快速部署（云端拉取，推荐）

将本项目代码推送到 GitHub 仓库后（示例 `TGap-Ruo/SafeStudy`），在服务器上执行 `deploy.sh` 即可完成全部部署。

**环境依赖安装**（Python venv、Chrome、防火墙等）**、代码拉取、服务注册与启动全部自动完成。**

### 1. 服务器上一条命令部署（最快）

SSH 登录服务器后，直接复制粘贴下面这一条命令即可：

```bash
curl -fsSL https://raw.githubusercontent.com/TGap-Ruo/SafeStudy/main/deploy.sh | sudo bash

#国内服务器
curl -fsSL https://gitee.com/tgap/safe-study/raw/main/deploy.sh | sudo bash

```

脚本会实时从公开仓库拉取代码并完成环境安装、服务注册与启动。整个过程无需在服务器上预先准备任何文件，适合全新服务器或重装后快速恢复。

> 前提：仓库保持**公开**且已推送最新代码（含 `deploy.sh`）。如 GitHub 连接较慢，可改用方式二先下载脚本再本地执行。

如果想把脚本保存到服务器上（方便以后重复执行做更新）：

```bash
curl -fsSL https://raw.githubusercontent.com/TGap-Ruo/SafeStudy/main/deploy.sh -o /root/deploy.sh
sudo bash /root/deploy.sh
```

### 2. 上传脚本后部署（通用）

```bash
# 在本机执行（把 IP 换成你的服务器）
scp deploy.sh root@你的服务器IP:/root/

# 再登录服务器执行
ssh root@你的服务器IP
sudo bash /root/deploy.sh
```

### 3. 部署脚本做了什么

1. 检查 root 权限与服务器架构
2. 安装系统依赖：`python3/venv/pip`、`wget`、`unzip`、`curl`、`rsync`
3. 未安装时自动下载安装 Google Chrome 官方 deb
4. 从 GitHub 公开仓库下载源码
5. 同步代码到 `/www/wwwroot/weban-web`（**自动保留**已有的 `logs/`、`tasks.json`、`venv/`）
6. 创建 Python 虚拟环境并安装依赖
7. 注册并启动两个 systemd 服务（均开机自启）：
   - `weban-cdp-chrome`：以 `--no-sandbox` 启动 Chrome CDP（127.0.0.1:9222）
   - `weban-web`：Web 服务（root + CDP 连接模式）
8. 防火墙放行 `5000/tcp`
9. 健康检查并打印访问地址

### 4. 部署选项（环境变量）

```bash
# 示例：自定义仓库、分支、安装目录，跳过系统依赖安装
REPO=TGap-Ruo/SafeStudy BRANCH=main APP_DIR=/www/wwwroot/weban-web \
SKIP_INSTALL=1 sudo -E bash /root/deploy.sh
```

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `REPO` | `TGap-Ruo/SafeStudy` | GitHub 仓库（owner/name） |
| `BRANCH` | `main` | 拉取分支 |
| `APP_DIR` | `/www/wwwroot/weban-web` | 安装目录 |
| `SKIP_INSTALL` | `0` | 设为 `1` 跳过系统依赖/Chrome 安装 |

---

## 浏览器运行模式（重要概念）

WeBan 需要 Chrome 浏览器执行任务。Google Chrome 的沙箱**不允许 root 用户直接启动**，而云服务器/宝塔面板默认用 root 运行服务。本项目提供两种模式：

### 模式 A：root + CDP 远程浏览器（deploy.sh 默认）

用一个带 `--no-sandbox` 的 Chrome CDP 实例（127.0.0.1:9222）充当浏览器，WeBan 任务通过 CDP 协议连接它，不再自己拉起 Chrome——与上游官方 Docker 镜像的做法一致。

```ini
# weban-web.service 中的关键配置
Environment="WEBBAN_CDP_HOST=127.0.0.1"
Environment="WEBBAN_CDP_PORT=9222"
```

### 模式 B：非 root 用户运行（更安全，可选）

Chrome 沙箱对普通用户正常可用，无需 `--no-sandbox` 和 CDP：

```bash
# 服务器上以 root 执行
useradd -m -s /usr/sbin/nologin weban
chown -R weban:weban /www/wwwroot/weban-web
```

然后编辑 `/etc/systemd/system/weban-web.service`：

```ini
User=weban
Group=weban
Environment="HOME=/home/weban"
# 删除下面两行 CDP 配置（不需要了）
# Environment="WEBBAN_CDP_HOST=127.0.0.1"
# Environment="WEBBAN_CDP_PORT=9222"
```

```bash
systemctl daemon-reload && systemctl restart weban-web
```

> 若 Chrome 安装路径非默认，可通过 `WEBBAN_CHROME_PATH` 环境变量指定（两种模式均适用）。

---

## 日常服务管理

部署完成后，服务器重启或日常维护都使用 `start-server.sh`：

```bash
cd /www/wwwroot/weban-web
sudo ./start-server.sh            # 启动（同 start）
sudo ./start-server.sh start      # 启动 Chrome CDP + Web
sudo ./start-server.sh stop       # 全部停止
sudo ./start-server.sh restart    # 全部重启
sudo ./start-server.sh status     # 查看状态（无需 root）
```

脚本优先使用 systemd；若检测不到服务文件（如容器内），会自动回退到 nohup 后台方式运行（日志 `logs/web.log`）。

常用运维命令：

```bash
systemctl status weban-web weban-cdp-chrome   # 服务状态
journalctl -u weban-web -f                    # Web 实时日志
journalctl -u weban-cdp-chrome -f             # Chrome CDP 日志
tail -f /www/wwwroot/weban-web/logs/chrome-cdp.log
```

---

## 使用说明

1. 浏览器访问 `http://服务器IP:5000`
2. 选择程序类型：
   - **WeBan 安全微伴**：学校需填**登录页显示的全称**（推荐直接复制）
   - **江苏安全平台**：学校支持关键词
3. 填写账号/密码，点击「启动任务」
4. 右侧实时终端查看进度；左侧任务列表可查看状态、停止、删除、下载日志

任务数据与日志目录：

| 内容 | 路径 |
|------|------|
| 单个任务日志 | `logs/<任务ID>/run.log` |
| WeBan 任务数据（config.toml、answer 等） | `logs/<任务ID>/` |
| Chrome CDP 日志 | `logs/chrome-cdp.log` |
| 任务记录 | `tasks.json` |

> 任务日志中的 `config.toml 不存在，正在下载远程模板...已创建空配置模板` 属于正常提示：账号由网页/命令行提供，无需理会模板中的账号字段。

---

## 反向代理与访问密码（强烈建议）

Web 服务默认裸跑在 5000 端口，**公网使用前请务必加访问密码并开启 HTTPS**。推荐 Nginx 反向代理 + BasicAuth：

```nginx
server {
    listen 443 ssl;
    server_name 你的域名;
    # ssl_certificate / ssl_certificate_key 配置略

    auth_basic "请输入访问密码";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE 实时输出必需（不能删）
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400;
    }
}
```

```bash
htpasswd -c /etc/nginx/.htpasswd 你的用户名   # 生成密码文件
ufw allow 80,443/tcp
```

> 9222 端口只允许本机访问（默认监听 127.0.0.1），**切勿对公网开放**。

---

## 更新项目

重新运行部署脚本即可（自动拉取最新代码、重启服务、保留数据）：

```bash
sudo bash /root/deploy.sh
```

手动部署用户可参考 `DEPLOY.md` 或用以下方式：

```bash
cd /www/wwwroot/weban-web
sudo systemctl stop weban-web
# 上传新代码覆盖（保留 logs/、tasks.json、venv/）
sudo systemctl start weban-web
```

---

## 卸载

```bash
systemctl disable --now weban-web weban-cdp-chrome
rm -f /etc/systemd/system/weban-web.service /etc/systemd/system/weban-cdp-chrome.service
systemctl daemon-reload
# 删除项目（按需）
# rm -rf /www/wwwroot/weban-web
```

---

## 常见问题（FAQ）

### Q1: 任务日志出现 `Failed to connect to browser ... pass no_sandbox=True`

服务以 root 运行导致 Chrome 沙箱无法启动。**使用 deploy.sh 默认 CDP 模式即可解决**；如未生效，检查：

```bash
journalctl -u weban-cdp-chrome      # Chrome CDP 服务是否正常
./cdp-chrome.sh status
curl http://127.0.0.1:9222/json/version
```

并确认 `weban-web.service` 中设置了 `WEBBAN_CDP_HOST` / `WEBBAN_CDP_PORT`。也可以改用非 root 用户运行（见上文「模式 B」）。

### Q2: 任务启动后立即失败

下载该任务日志查看原因，常见情况：

- 学校名称错误（WeBan 需与登录页完全一致）
- 账号密码错误
- 服务器无法访问目标平台（网络不通）
- Chrome 未安装或 CDP 未就绪

### Q3: 端口 5000 被占用

```bash
lsof -i :5000
```

杀掉占用进程后重启；如需换端口，修改 `weban-web.service` 的 `Environment="PORT=xxxx"` 并同步防火墙规则。

### Q4: ARM 服务器能用吗？

仓库内为 x86_64 二进制。ARM 需下载对应 arm64 版 `WeBan-linux-arm64` 替换 `programs/weban/WeBan-linux-x64`。

### Q5: `python3 -m venv venv` 报错 `ensurepip is not available`

```bash
apt install -y python3-venv        # 版本号按实际调整，如 python3.12-venv
```

### Q6: 服务器重启后服务没自动启动

```bash
systemctl is-enabled weban-web weban-cdp-chrome   # 应输出 enabled
systemctl enable --now weban-web weban-cdp-chrome # 未启用则补上
```

### Q7: 多开内存不足

WeBan 每个实例约 200-400MB：1GB 内存建议最多 1-2 个任务，2GB 建议 3-4 个；江苏安全平台占用极低（<50MB）。

---

## 详细文档

更多运维细节（systemd 手动配置、内网穿透、Nginx、更新 WeBan 二进制等）见 [`DEPLOY.md`](DEPLOY.md)。
