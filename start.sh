#!/bin/bash
# 生产排程系统 一键启动脚本（Ubuntu 适配，依赖增量安装）
# 用法: ./start.sh [端口]   (默认端口 8899)

set -e
cd "$(dirname "$0")"

PORT="${1:-8899}"

echo "========================================"
echo "  生产排程系统启动器"
echo "========================================"

# 1. 检查 python3
if ! command -v python3 &>/dev/null; then
  echo "[错误] 未检测到 python3，Ubuntu 请先安装：sudo apt install python3"
  exit 1
fi

# 2. 检查 venv 模块（Ubuntu 需装 python3-venv）
if ! python3 -c "import venv" &>/dev/null; then
  echo "[错误] 缺少 python3-venv 模块"
  echo "       Ubuntu 请执行: sudo apt install python3-venv"
  exit 1
fi

# 3. 创建虚拟环境（仅缺失时创建）
if [ ! -d "venv" ]; then
  echo "[信息] 首次运行，创建虚拟环境 venv ..."
  python3 -m venv venv
  # 新环境先升 pip 与已装 wheel，避免安装报错
  ./venv/bin/pip install --upgrade pip wheel -q
else
  echo "[信息] 虚拟环境已存在，跳过创建"
fi

# 4. 检测缺失依赖，仅安装缺失部分
echo "[信息] 检测依赖是否缺失 ..."
MISSING=$(./venv/bin/python check_deps.py 2>/dev/null)
if [ -n "$MISSING" ]; then
  echo "[信息] 检测到缺失依赖，正在安装: ${MISSING}"
  # shellcheck disable=SC2086
  ./venv/bin/pip install $MISSING -q
  echo "[信息] 依赖安装完成"
else
  echo "[信息] 依赖已齐全，跳过安装"
fi

# 5. 启动服务
echo "----------------------------------------"
echo "[信息] 启动服务，监听端口 ${PORT}"
echo "[信息] 访问地址: http://<服务器IP>:${PORT}"
echo "[信息] 首次启动会自动创建管理员账号 admin，初始密码见下方日志输出"
echo "----------------------------------------"
exec ./venv/bin/python backend/main.py --port "${PORT}"
