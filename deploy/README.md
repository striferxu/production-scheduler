# 生产排程系统 v1.0 — 部署文档

> 面向本地 Linux 服务器部署（适配 Ubuntu），使用 systemd 管理服务，开机自启、崩溃自动重启。
> 支持**增量依赖安装**：启动时会先检测缺失依赖，仅安装缺失部分，已安装的直接跳过。

## 目录
- [一、环境要求](#一环境要求)
- [二、快速部署](#二快速部署)
- [三、增量依赖安装机制](#三增量依赖安装机制)
- [四、用户角色与权限](#四用户角色与权限)
- [五、示例数据（一键载入）](#五示例数据一键载入)
- [六、后台常驻运行（开机自启）](#六后台常驻运行开机自启)
- [五、外网/局域网访问](#五外网局域网访问)
- [六、数据管理](#六数据管理)
- [七、端口修改](#七端口修改)
- [八、常见问题](#八常见问题)

---

## 一、环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Linux（适配 Ubuntu / CentOS / Debian） |
| Python | 3.10 及以上 |
| 虚拟环境模块 | Python 自带 `venv`（Ubuntu 缺省需安装，见下） |
| 端口 | 默认 8899（可自定义） |
| 数据库 | 内置 SQLite，无需额外安装 |

### Ubuntu 前置检查

Ubuntu 的 Python3 默认不带 `venv` 模块，先确认：

```bash
python3 --version          # 需 >= 3.10
python3 -m venv -h &>/dev/null && echo "venv 可用" || echo "需安装 python3-venv"

# 若输出「需安装 python3-venv」，执行：
sudo apt update
sudo apt install -y python3-venv python3-pip
```

---

## 二、快速部署

### 1. 上传并解压

```bash
cd /opt
tar -zxvf production-scheduler.tar.gz
cd production-scheduler
chmod +x start.sh
```

### 2. 启动

```bash
./start.sh          # 默认端口 8899
# 或指定端口：
./start.sh 9000
```

**首次运行**自动完成：创建虚拟环境 → 检测并安装缺失依赖 → 创建管理员账号 → 启动服务。
之后的运行会跳过已就绪的步骤，直接启动。

### 3. 访问

浏览器打开：`http://<服务器IP>:8899`

- **API 文档**：`http://<服务器IP>:8899/docs`

---

## 三、增量依赖安装机制

`start.sh` 并非每次全量安装依赖，而是按顺序做**最小必要操作**：

| 步骤 | 动作 | 触发条件 |
|------|------|---------|
| 1. 检查 python3 | 无则在终端报错并给安装命令 | python3 不存在 |
| 2. 检查 venv 模块 | 报错并提示 Ubuntu 安装命令 | 缺 `python3-venv` |
| 3. 创建虚拟环境 | `python3 -m venv venv` | `venv/` 目录不存在才创建 |
| 4. **检测缺失依赖** | 用 `check_deps.py` 逐个检测 | 始终执行，但只列出缺失项 |
| 5. **仅安装缺失项** | `pip install 缺失包...` | **仅当检测到缺失时** |
| 6. 启动服务 | `python main.py --port 8899` | 始终执行 |

### `check_deps.py` 说明

- 读取 `requirements.txt`，逐个包检测是否已能 `import`
- 已安装的包**不联网、不重装**，秒过
- 正确处理带 extra/版本约束的写法，如 `passlib[bcrypt]>=1.7`
- 处理 import 名与 pip 名不一致的包（如 `python-multipart` → `multipart`）

### 典型输出对照

**首次运行**（venv 全新，需装依赖）：
```
[信息] 首次运行，创建虚拟环境 venv ...
[信息] 检测依赖是否缺失 ...
[信息] 检测到缺失依赖，正在安装: fastapi uvicorn sqlalchemy ...
[信息] 依赖安装完成
```

**后续运行**（依赖齐全，直接启动，无需联网）：
```
[信息] 虚拟环境已存在，跳过创建
[信息] 检测依赖是否缺失 ...
[信息] 依赖已齐全，跳过安装
----------------------------------------
[信息] 启动服务，监听端口 8899
```

---

## 四、用户角色与权限

系统采用登录鉴权（JWT），按角色分级授权：

| 角色 | 权限 |
|------|------|
| **管理员 admin** | 一切权限：维护全部基础数据、管理用户账号、设置设备/人员日历、备份恢复、导入导出 |
| **普通用户**（车间主任/排产员） | 仅可查看数据、执行排产、查看/拖拽甘特图、导出派工单；**不能修改基础数据**（后端会返回 403） |

**要点**：
- 未登录访问任何接口都会返回 401
- 普通用户界面上会自动隐藏「基础数据」入口，且即使直接调用接口也会被后端拒绝
- 系统启动自动创建管理员 `admin`，初始密码随机生成并打印在启动日志（或 `ADMIN_PASSWORD=*** ./start.sh` 预设）
- 管理员在「基础数据 → 用户」页面创建普通用户账号

## 五、示例数据（一键载入）

全新部署（空库）后，管理员可在「基础数据」页点击 **🎯 载入示例数据**，一键生成一套演示数据：

- 3 个产品（刹车片/方向盘/排气管）、3 条工艺路线
- 2 个设备组、4 台设备、3 道工序（支持并行拆分）
- 班次（早/中/晚）与人员组别、5 名员工及技能矩阵

载入后可直接到「排程执行」页选择产品 → 输入数量/交期 → 自动排程 → 甘特图查看，快速完整体验系统。

> ⚠️ 示例数据仅在基础数据为空时可用，避免覆盖用户真实数据。

## 六、后台常驻运行（开机自启）



### 方式 A：systemd（推荐）

```bash
# 1. 把 service 文件放到系统目录
sudo cp deploy/production-scheduler.service /etc/systemd/system/

# 2. 编辑路径（若部署目录不是 /opt/production-scheduler 需修改）
sudo vim /etc/systemd/system/production-scheduler.service
#    改 WorkingDirectory 和 ExecStart 两行为你的实际路径

# 3. 启用并启动
sudo systemctl daemon-reload
sudo systemctl enable production-scheduler   # 开机自启
sudo systemctl start production-scheduler    # 立即启动

# 4. 查看状态和日志
sudo systemctl status production-scheduler
sudo journalctl -u production-scheduler -f
```

> **注意**：首次启动若走 systemd，管理员初始密码会打印在该服务的启动日志里，用
> `sudo journalctl -u production-scheduler` 查看最早几行即可。

### 方式 B：nohup 后台运行（简单）

```bash
cd /opt/production-scheduler
nohup ./venv/bin/python backend/main.py --port 8899 > app.log 2>&1 &
```

---

## 七、外网/局域网访问

| 场景 | 做法 |
|------|------|
| 局域网（车间内） | 直接 `http://服务器内网IP:8899` |
| 外网 | 需服务器有**公网IP**，或路由器**端口转发** 8899，或内网穿透 |
| 绑定域名 + HTTPS | 配置 Nginx 反向代理：`server{ listen 80; server_name 你的域名; location / { proxy_pass http://127.0.0.1:8899; } }` |

### Ubuntu 防火墙放行（ufw）

```bash
sudo ufw allow 8899/tcp
sudo ufw reload
```

**安全提醒**：系统自带登录鉴权（未登录不可访问）。管理员账号 `admin` 的初始密码**自动生成**并打印在启动日志中，登录后请**尽快在「基础数据 → 用户」里修改密码**，并创建普通用户账号供车间主任/排产员使用。

---

## 八、数据管理

- **数据库文件**：`data/scheduler.db`（SQLite，自动创建）
- **备份**：系统内「基础数据」页有手动备份功能；也可直接备份 `data/scheduler.db` 文件
- **导出**：派工单 Excel、基础数据 Excel 导出到 `exports/` 目录
- **上传文件**：基础数据支持 Excel 模板下载与批量导入

---

## 九、端口修改

改端口只需启动时传参：

```bash
./start.sh 9000
# 或 systemd 方式：修改 service 文件 ExecStart 的 --port 后重启
```

> 改端口后访问地址相应变为 `http://服务器IP:新端口`，防火墙也要放行新端口。

---

## 十、常见问题

| 问题 | 解决 |
|------|------|
| `venv` 创建失败 | Ubuntu：`sudo apt install python3-venv`；CentOS：`sudo yum install python3-devel` |
| 提示「缺少 python3-venv」 | 见上文前置检查，安装后重跑 `./start.sh` |
| 端口被占用 | `./start.sh 9000` 换端口；或 `sudo kill $(sudo lsof -t -i:8899)` |
| 外网打不开 | 检查防火墙：`sudo ufw allow 8899/tcp && sudo ufw reload`；云服务器还需在控制台安全组放行端口 |
| 忘记/丢失管理员密码 | 停服后删除 `data/scheduler.db` 重建（会清空数据），或用已有管理员在系统内新建；也可停服后用 `ADMIN_PASSWORD=新密码 ./start.sh` 重置（仅当库里没有用户时生效） |
| 手动预设初始密码 | `ADMIN_PASSWORD=你的密码 ./start.sh`（仅首次创建管理员时生效） |
| 依赖装了一半失败 | 重新 `./start.sh`，增量机制会自动补齐剩余缺失项 |
