# 生产排程系统（APS）v1.0

一个面向中小型制造车间、本地私有化部署的**有限产能生产排程系统（APS）**。
基于 FastAPI + SQLite 构建，原生前端单页应用，无需额外数据库与复杂环境，解压即用。

> 部署文档（systemd 开机自启 / 防火墙 / 外网访问）详见 [`deploy/README.md`](deploy/README.md)。
> 本仓库同时提供可直接部署的完整包 `production-scheduler.tar.gz`。

---

## ✨ 功能特性

- **有限产能排程引擎**：同时考虑**设备**与**人员**双重约束，支持任务**并行拆分**、**跨天拆分**
- **甘特图可视化**：设备视图 / 人员视图双视角，支持**拖拽调整**任务、拖拽后**联动重算**
- **基础数据全量管理**：产品、设备组/设备、工序、工艺路线、班次、轮班规则、员工组别/员工及技能矩阵
- **排程执行**：选择产品 → 输入数量/交期 → 自动排程 → 甘特图查看与调整，支持锁单、重排
- **JWT 登录鉴权**：管理员 / 普通用户两级角色，后端强制校验（写接口仅管理员）
- **Excel 生态**：派工单导出、基础数据模板下载与批量导入、全量数据导出
- **备份恢复**：数据库一键手动备份 + 恢复
- **示例数据一键载入**：空库时一键生成整套演示数据，快速完整体验
- **增量依赖安装**：`start.sh` 自动检测缺失依赖，仅安装缺失部分，无需全程联网

---

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.10+ / FastAPI / uvicorn |
| ORM | SQLAlchemy 2.x |
| 数据库 | SQLite（零配置，`data/scheduler.db`） |
| 鉴权 | JWT（passlib[bcrypt] 哈希密码） |
| 前端 | 原生 HTML / CSS / JavaScript（SPA，无构建步骤） |
| 导出 | openpyxl（Excel） |

---

## 📁 目录结构

```
production-scheduler/
├── backend/
│   ├── main.py                     # FastAPI 应用入口，全部 API 路由
│   ├── auth.py                     # JWT 生成 / 当前用户 / 鉴权依赖
│   ├── models/
│   │   ├── database.py             # SQLite 引擎与会话
│   │   └── all_models.py           # 全部 ORM 数据模型
│   └── services/
│       └── scheduler_engine.py     # 有限产能排程引擎（核心算法）
├── frontend/
│   ├── index.html                  # 单页应用入口
│   └── css/style.css               # 样式
├── deploy/
│   ├── README.md                   # 生产部署文档
│   └── production-scheduler.service # systemd 服务单元
├── requirements.txt                # Python 依赖清单
├── check_deps.py                   # 缺失依赖检测脚本（start.sh 调用）
├── start.sh                        # 一键启动脚本（增量装依赖）
├── data/                           # 运行时数据库（自动创建，不入库）
├── backups/                        # 备份目录（自动创建，不入库）
├── exports/                        # Excel 导出目录（自动创建，不入库）
└── production-scheduler.tar.gz     # 完整部署包
```

---

## 🚀 快速开始

### 方式一：本地开发 / 体验

```bash
# 1. 克隆或下载源码
git clone <仓库地址> production-scheduler
cd production-scheduler

# 2. 一键启动（自动：建 venv → 增量装依赖 → 启动）
./start.sh            # 默认端口 8899
# 或指定端口
./start.sh 9000
```

- 访问界面：`http://localhost:8899`
- API 文档（Swagger UI）：`http://localhost:8899/docs`

**首次运行**会自动创建管理员账号 `admin`，**初始密码随机生成并打印在启动日志中**，
也可用环境变量预设初始密码：

```bash
ADMIN_PASSWORD=你的密码 ./start.sh
```

> ⚠️ 登录后请尽快在「基础数据 → 用户」里修改管理员密码，并创建普通用户供车间人员使用。

### 方式二：生产部署（推荐）

使用 `production-scheduler.tar.gz` 部署到 Linux 服务器，并配合 systemd 实现**开机自启、崩溃自动重启**。
完整步骤（含防火墙、外网访问、密码管理）见 [`deploy/README.md`](deploy/README.md)。

```bash
cd /opt
tar -zxvf production-scheduler.tar.gz
cd production-scheduler
chmod +x start.sh
sudo cp deploy/production-scheduler.service /etc/systemd/system/
# 按需修改 service 中的 WorkingDirectory / ExecStart 路径后：
sudo systemctl daemon-reload
sudo systemctl enable --now production-scheduler
```

---

## 🎯 排程引擎说明

核心算法位于 `backend/services/scheduler_engine.py`，采用**有限产能（Finite Capacity）**思路：

- **双重资源约束**：任务排程同时受设备（产能、可用时段）与人员（技能、人员可用性）约束
- **并行拆分**：可将较大批量按设备/人员能力拆分为多个并行子任务，缩短总周期
- **跨天拆分**：单任务可跨班次/跨天排程，自动衔接时间
- **拖拽联动重算**：甘特图上拖拽任务后，系统自动重新计算受影响任务的时间与资源占用

**排程输入**：产品（对应工艺路线） + 数量 + 交期
**排程输出**：各工序任务的时间安排、设备/人员指派、批量号 `batch_id`，并给出**逾期预警**报告。

---

## 👥 用户角色与权限

| 角色 | 说明 | 权限 |
|------|------|------|
| **admin** | 管理员 | 全部权限：维护基础数据、用户管理、备份恢复、导入导出、执行排程 |
| **user** | 普通用户（车间主任/排产员） | 查看数据、执行排程、甘特图拖拽、导出派工单；**不能修改基础数据**（后端返回 403） |

- 未登录访问任何接口返回 `401`
- 普通用户界面自动隐藏「基础数据」入口，即使直接调用接口也会被后端拒绝（JWT 校验）

---

## 🧩 核心 API 概览

统一前缀在 `backend/main.py` 中定义。完整接口定义见 `/docs`（Swagger）：

| 分组 | 方法/路径 | 说明 |
|------|-----------|------|
| 认证 | `POST /api/auth/login` | 登录，返回 JWT token |
| 认证 | `POST /api/auth/register` | 创建用户（仅管理员） |
| 基础数据 | `/api/product-categories` `/api/products` `/api/device-groups` `/api/devices` `/api/processes` `/api/product-routes` `/api/shifts` `/api/rotations` `/api/employee-groups` `/api/employees` | 增删改查（写接口仅 admin，读接口登录即可） |
| 用户 | `/api/users` | 用户管理（仅 admin） |
| 排程 | `POST /api/schedule/run` | 执行排程 |
| 排程 | `GET /api/schedule/tasks` | 查询排程任务 |
| 排程 | `GET /api/schedule/batches` | 查询排程批次 |
| 排程 | `POST /api/schedule/tasks/{id}/lock` | 锁定任务 |
| 排程 | `POST /api/schedule/tasks/{id}/move` | 拖拽移动任务（联动重算） |
| 排程 | `POST /api/schedule/rerun` | 重新排程 |
| 导出 | `POST /api/export/excel` | 导出派工单 Excel |
| 导出 | `GET /api/export/excel-template/{entity}` | 下载基础数据导入模板 |
| 导出 | `GET /api/export/all-data` | 导出全部基础数据 |
| 导入 | `POST /api/import/excel` | Excel 批量导入基础数据 |
| 备份 | `POST /api/backup/create` | 手动备份数据库 |
| 备份 | `POST /api/backup/restore/{id}` | 恢复备份 |
| 示例 | `POST /api/seed/demo` | 一键载入示例数据（空库时） |
| 选项 | `GET /api/options/{entity}` | 下拉选项数据 |

---

## 🗄 数据管理

| 项 | 说明 |
|----|------|
| 数据库文件 | `data/scheduler.db`（SQLite，首次启动自动创建） |
| 备份 | 系统内手动备份到 `backups/`；也可直接复制 `data/scheduler.db` |
| 导出 | 派工单 / 基础数据 Excel 输出到 `exports/` |
| 导入 | 基础数据支持模板下载 + Excel 批量导入 |

---

## ⚙️ 常见配置

- **改端口**：`./start.sh 9000`，或修改 systemd service 的 `ExecStart --port`
- **预设管理员密码**：`ADMIN_PASSWORD=xxx ./start.sh`
- **增量依赖机制**：`check_deps.py` 逐个检测 `requirements.txt` 中的包，`start.sh` 仅安装缺失项

---

## 📦 部署包说明

`production-scheduler.tar.gz` 为本系统**完整部署包**，内容与源码一致，额外剔除了运行时数据
（`data/`、`backups/`、`exports/`、`venv/`），可直接解压部署到干净服务器。

查看包内结构：

```bash
tar -tzf production-scheduler.tar.gz
```

若源码有更新，需重新打包后再分发：

```bash
tar -czf production-scheduler.tar.gz \
  --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='data' --exclude='backups' --exclude='exports' \
  backend frontend deploy requirements.txt start.sh check_deps.py
```

---

## 📄 许可证与免责声明

- 本系统供内部使用，开源发布仅供学习/自用参考，**请在部署前自行评估安全与合规风险**
- 涉及生产业务数据时，请务必：修改默认密码、限制访问、定期备份数据库
- 「过往/示例数据」均非真实业务数据
