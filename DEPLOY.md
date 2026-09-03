# 自动化任务管理平台 - 部署指南（纯二进制版）

## 项目简介

将 **WeBan（安全微伴）** 和 **江苏安全平台** 两个自动化脚本封装为 Web 服务，支持：
- 网页端输入学校、账号、密码，一键启动
- 后台多开（多个账号同时运行，互不干扰）
- 实时终端输出显示（SSE 推送）
- 运行日志持久化，可下载
- 任务管理（停止、删除、状态查看）

> **本版本 WeBan 使用编译好的 Linux 二进制可执行文件**，无需安装 nodriver/opencv/numpy 等复杂 Python 依赖，部署更简单，运行更稳定。
>
> ⚠️ **系统要求：Ubuntu 24.04+（GLIBC 2.38+）**。二进制文件在此系统上编译，Ubuntu 22.04 及以下系统无法运行。

---

## 一、环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | **Ubuntu 24.04+**（GLIBC 2.38+，WeBan 二进制必需） |
| Python | 3.8+（系统自带即可，仅 Web 服务需要） |
| 内存 | 最低 1GB（多开建议 2GB+） |
| 磁盘 | 至少 200MB 可用空间 |

> ⚠️ **重要**：WeBan 二进制文件需要 GLIBC 2.38+，Ubuntu 22.04 及以下系统无法运行。如你的系统是 Ubuntu 22.04，请使用 Python 源码版本。

> **注意**：WeBan 二进制是 x86_64 架构，ARM 服务器（如树莓派、ARM 云服务器）需要使用 WeBan-linux-arm64 版本替换。

---

## 二、安装系统依赖

### 2.1 安装 Python venv 支持

```bash
apt update
apt install -y python3.10-venv wget
```
> 如果你的系统 Python 不是 3.10，用 `python3 --version` 查看版本，然后安装对应版本的 venv 包（如 python3.11-venv）。

### 2.2 安装 Google Chrome（WeBan 运行必需）

> **不要安装 snap 版 chromium！** snap 沙盒会导致 nodriver 无法控制浏览器。直接安装 Google Chrome 官方 deb 包。

```bash
# 下载 Google Chrome 稳定版
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

# 安装
dpkg -i google-chrome-stable_current_amd64.deb

# 修复依赖（dpkg -i 可能报依赖缺失，执行这条自动修复）
apt -f install -y
```

验证安装：
```bash
google-chrome-stable --version
which google-chrome-stable
```
> 应输出 `/usr/bin/google-chrome-stable`，程序默认使用这个路径。

> 如果 Chrome 安装在其他路径，可通过环境变量 `WEBBAN_CHROME_PATH` 指定，在 systemd 服务文件中添加：
> ```ini
> Environment="WEBBAN_CHROME_PATH=/你的/chrome/路径"
> ```

---

## 三、上传并解压项目

1. 将 `weban-web.zip` 上传到服务器（如 `/www/wwwroot/` 目录）
2. 解压：
```bash
cd /www/wwwroot/
unzip weban-web.zip
cd weban-web
```

3. 确认 WeBan 二进制文件存在并有执行权限：
```bash
ls -lh programs/weban/WeBan-linux-x64
```
> 如果没有执行权限，执行：`chmod +x programs/weban/WeBan-linux-x64`

---

## 四、部署 Web 服务

### 4.1 创建 Python 虚拟环境并安装依赖

```bash
cd /www/wwwroot/weban-web

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 确认虚拟环境路径正确（必须输出 /www/wwwroot/weban-web/venv/bin/python3）
which python3

# 安装依赖（仅需 flask 和 requests，非常轻量）
python3 -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4.2 本地测试启动

```bash
python3 app.py
```
看到输出 `* Running on http://0.0.0.0:5000` 代表程序正常，按 `Ctrl+C` 停止。

> 如果报 `Address already in use`，说明 5000 端口被占用，执行 `lsof -i :5000` 查看占用进程，杀掉后重试。

### 4.3 配置 systemd 后台常驻运行（推荐）

```bash
nano /etc/systemd/system/weban-web.service
```

粘贴以下内容：
```ini
[Unit]
Description=WeBan Web Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/www/wwwroot/weban-web
ExecStart=/www/wwwroot/weban-web/venv/bin/python3 app.py
Restart=on-failure
RestartSec=5
Environment="PYTHONUNBUFFERED=1"
# 如 Chrome 路径非默认，取消下面注释并修改路径
# Environment="WEBBAN_CHROME_PATH=/usr/bin/google-chrome-stable"
# 如以 root 运行且不想换用户，取消下面注释并按 4.4 方案B 启动 CDP Chrome
# Environment="WEBBAN_CDP_HOST=127.0.0.1"
# Environment="WEBBAN_CDP_PORT=9222"

[Install]
WantedBy=multi-user.target
```

保存退出：`Ctrl+O` 回车，`Ctrl+X`

启动服务并设置开机自启：
```bash
systemctl daemon-reload
systemctl start weban-web
systemctl enable weban-web
systemctl status weban-web
```
看到绿色 `active (running)` 代表服务正常运行。

查看实时日志：
```bash
journalctl -u weban-web -f
```

> ⚠️ **root 用户注意**：以 root 运行本服务时，WeBan 任务会报
> `Failed to connect to browser ... pass no_sandbox=True`（Chrome 沙箱不允许 root）。
> 必须按下方 **4.4** 处理（改用非 root 用户，或配置 CDP 模式），否则任务无法启动浏览器。

### 4.4 root 环境下的 Chrome 沙箱问题（重要）

**现象**：任务日志出现：

```text
浏览器检测失败: 浏览器启动失败:
Failed to connect to browser
One of the causes could be when you are running as root.
In that case you need to pass no_sandbox=True
```

**原因**：Google Chrome 的沙箱不允许 root 用户直接启动；而 WeBan 二进制由
nodriver 自己拉起 Chrome 且不会附加 `--no-sandbox`。宝塔面板 / 云服务器常用
root 运行 systemd 服务，最容易踩到这个坑。

**方案 A：改用非 root 用户运行服务（最推荐）**

Chrome 沙箱对普通用户正常可用，无需关闭沙箱，最安全。宝塔环境可直接用
`www` 用户，独立服务器可新建用户：

```bash
# 创建专用用户（宝塔环境已有 www 用户则跳过）
useradd -m -s /usr/sbin/nologin weban

# 授权项目目录（宝塔环境用户改为 www）
chown -R weban:weban /www/wwwroot/weban-web

# 修改 /etc/systemd/system/weban-web.service：
#   User=root           →  User=weban
#   并补充 HOME 环境变量（Chrome 需要可写的 HOME）：
#   Environment="HOME=/home/weban"     （宝塔 www 用户则填 /home/www）
```

```bash
systemctl daemon-reload && systemctl restart weban-web
```

**方案 B：root 环境改用 CDP 模式（不想换用户时）**

WeBan 支持连接外部 CDP 浏览器，与官方 Docker 镜像的做法一致：先用
`--no-sandbox` 单独拉起一个 Chrome CDP 实例，任务再通过
`WEBBAN_CDP_HOST` / `WEBBAN_CDP_PORT` 连接它，不再自己启动浏览器。

```bash
cd /www/wwwroot/weban-web
./cdp-chrome.sh start     # 后台启动 Chrome CDP（默认 127.0.0.1:9222）
./cdp-chrome.sh status    # 验证进程
curl http://127.0.0.1:9222/json/version   # 应返回浏览器版本 JSON
```

然后在 `weban-web.service` 中添加环境变量并重启：

```ini
Environment="WEBBAN_CDP_HOST=127.0.0.1"
Environment="WEBBAN_CDP_PORT=9222"
```

```bash
systemctl daemon-reload && systemctl restart weban-web
```

> 设置了这两个变量后，所有 WeBan 任务都会走 CDP 连接，`--browser-path`
> （`WEBBAN_CHROME_PATH`）不再生效。

Chrome CDP 开机自启（可选但推荐，否则服务器重启后需手动 `./cdp-chrome.sh start`）：

```bash
nano /etc/systemd/system/weban-cdp-chrome.service
```

```ini
[Unit]
Description=WeBan CDP Chrome (no-sandbox)
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/www/wwwroot/weban-web
ExecStart=/www/wwwroot/weban-web/cdp-chrome.sh start
ExecStop=/www/wwwroot/weban-web/cdp-chrome.sh stop

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl start weban-cdp-chrome
systemctl enable weban-cdp-chrome
```

---

## 五、外网访问配置

### 情况A：服务器有独立公网IP

1. 开放防火墙端口：
```bash
ufw allow 5000/tcp
```
2. 云服务商控制台安全组也需要开放 5000 端口
3. 浏览器访问 `http://服务器IP:5000`

> **生产环境建议配置 Nginx 反向代理 + SSL 证书**，只开放 80/443 端口。

### 情况B：服务器无独立公网IP（需要内网穿透）

无公网IP必须使用内网穿透工具把本地 5000 端口暴露到公网。推荐以下三种：

#### 推荐1：cpolar（国内最省心，有免费版）

```bash
# 安装 cpolar
curl -L https://www.cpolar.com/static/downloads/install-release-cpolar.sh | sudo bash

# 注册账号获取 token：https://www.cpolar.com/
# 登录后在「验证」页面复制 authtoken，配置 token
cpolar authtoken 你的token值

# 启动 HTTP 隧道，映射本地 5000 端口
cpolar http 5000
```

启动后会显示公网地址，例如：
```
Forwarding  https://xxxx.r2.cpolar.cn -> http://localhost:5000
```
用浏览器访问这个 https 地址即可。

**配置后台常驻运行：**
编辑 `/usr/local/etc/cpolar/cpolar.yml`，在 `tunnels:` 下添加：
```yaml
tunnels:
  weban:
    proto: http
    addr: 5000
```
然后：
```bash
systemctl enable cpolar
systemctl start cpolar
```

#### 推荐2：frp（自建，完全免费稳定，需要一台有公网IP的中转服务器）

如果你有另一台带公网IP的服务器，用 frp 最稳定。配置方法见 frp 官方文档，客户端映射本地 5000 端口即可。

#### 推荐3：Cloudflare Tunnel（免费，需要域名）

如果你有域名且托管在 Cloudflare，可以用免费的 Cloudflare Tunnel。

---

## 六、设置网页访问密码（推荐）

无宝塔环境下，推荐两种方式：

### 方式一：安装 Nginx 配置 BasicAuth（推荐）

```bash
apt install -y nginx apache2-utils

# 创建密码文件（用户名为 admin，执行后输入密码）
htpasswd -c /etc/nginx/.htpasswd admin

# 创建站点配置
nano /etc/nginx/sites-available/weban
```

粘贴：
```nginx
server {
    listen 80;
    server_name 你的域名或IP;

    # BasicAuth 密码认证
    auth_basic "请输入访问密码";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE 实时输出必需配置（不能删掉）
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400;
    }
}
```

```bash
# 启用站点
ln -s /etc/nginx/sites-available/weban /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

> ⚠️ **务必开启 HTTPS（SSL 证书）**，BasicAuth 密码在 HTTP 下是明文传输的。

### 方式二：修改 app.py 代码增加简单登录校验

如果不想装 Nginx，可以在 Flask 代码里增加简单的登录校验。需要的话可以告诉我，我帮你加。

---

## 七、日志与数据

| 内容 | 路径 |
|------|------|
| 任务日志 | `/www/wwwroot/weban-web/logs/<任务ID>/run.log` |
| WeBan 数据 | `/www/wwwroot/weban-web/logs/<任务ID>/`（config、answer） |
| CDP Chrome 日志 | `/www/wwwroot/weban-web/logs/chrome-cdp.log`（CDP 模式下） |
| 任务记录 | `/www/wwwroot/weban-web/tasks.json` |
| 系统服务日志 | `journalctl -u weban-web -f` |

---

## 八、常用运维命令

```bash
# 重启服务（修改代码后执行）
systemctl restart weban-web

# 停止服务
systemctl stop weban-web

# 查看运行状态
systemctl status weban-web

# 查看实时日志
journalctl -u weban-web -f

# 查看最近 100 行日志
journalctl -u weban-web -n 100

# 进入虚拟环境（安装新依赖时）
cd /www/wwwroot/weban-web
source venv/bin/activate
```

---

## 九、常见问题

### Q1: WeBan 启动报错 "No browser found" 或浏览器启动失败
**A:** 先看任务日志中的具体报错：

如果包含 `Failed to connect to browser ... pass no_sandbox=True`，说明服务以
**root 运行**导致 Chrome 沙箱失败，按 **4.4** 处理（改用非 root 用户，或配置
CDP 模式并启动 `./cdp-chrome.sh start`）。

其他情况检查 Google Chrome 是否正确安装：
```bash
which google-chrome-stable
google-chrome-stable --version
```
如果路径不是 `/usr/bin/google-chrome-stable`，在 systemd 服务文件中添加环境变量：
```ini
Environment="WEBBAN_CHROME_PATH=/实际/chrome/路径"
```
然后 `systemctl daemon-reload && systemctl restart weban-web`。

### Q2: 实时输出不更新/卡住
**A:** 如果配置了 Nginx 反向代理，检查是否配置了 `proxy_buffering off` 和 `proxy_read_timeout 86400`。参考第六节。

### Q3: 多开时内存不够
**A:** WeBan 每个实例约占用 200-400MB 内存。建议：
- 1GB 内存：同时最多 1-2 个 WeBan 任务
- 2GB 内存：同时最多 3-4 个
- 江苏安全平台占用极低（<50MB），可大量并发

### Q4: 任务启动后立即失败
**A:** 点击任务的「日志」按钮下载日志查看，常见原因：
- 学校名称错误（WeBan 与江苏安全均需完整全称，江苏安全模糊词会匹配失败并提示相近学校）
- 账号密码错误
- 网络不通（服务器无法访问目标网站）
- Chrome 未安装或路径错误

### Q5: `python3 -m venv venv` 报错 "ensurepip is not available"
**A:** 缺少 venv 系统包，执行：
```bash
apt install -y python3.10-venv
```
（根据你的 Python 版本调整，如 python3.11-venv）

### Q6: ARM 服务器可以用吗？
**A:** 当前二进制是 x86_64 版本。ARM 服务器（如树莓派、ARM 云服务器）需要下载 WeBan-linux-arm64 版本，替换 `programs/weban/WeBan-linux-x64` 文件，并修改 `task_manager.py` 中的二进制文件名。

### Q7: 如何更新 WeBan 程序？
**A:** 下载新版本的 `WeBan-linux-x64` 二进制文件，替换 `programs/weban/` 目录下的旧文件，然后 `systemctl restart weban-web`。

---

## 十、安全建议

1. **务必配置访问密码**，不要裸奔公网
2. **务必开启 HTTPS**，BasicAuth 密码在 HTTP 下明文传输
3. **不要直接暴露 5000 端口**，配置 Nginx 反向代理后只开放 80/443
4. **定期清理日志**：日志会持续增长，建议定期清理 `logs/` 目录下的旧任务
5. **限制并发**：根据服务器配置合理控制同时运行的任务数

---

## 项目结构

```
weban-web/
├── app.py                  # Flask 主应用（API + SSE）
├── task_manager.py         # 任务管理器（进程、输出、日志）
├── cdp-chrome.sh           # 以 --no-sandbox 启动 Chrome CDP（root 环境用）
├── requirements.txt        # Python 依赖（仅 flask + requests）
├── start.sh                # 命令行启动脚本
├── programs/
│   ├── weban/
│   │   ├── WeBan-linux-x64  # WeBan 编译好的二进制可执行文件（核心）
│   │   ├── answer/          # 题库
│   │   ├── captcha_model.onnx  # 验证码模型
│   │   ├── config.example.toml
│   │   └── LICENSE
│   └── safety/             # 江苏安全平台（Python 脚本 + 非交互包装）
├── templates/
│   └── index.html          # 前端页面
├── logs/                   # 任务日志（运行后生成）
├── tasks.json              # 任务记录（运行后生成）
└── DEPLOY.md               # 本文档
```
