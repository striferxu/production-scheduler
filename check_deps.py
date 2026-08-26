#!/usr/bin/env python3
"""检测 requirements.txt 中缺失的依赖，仅输出缺失的包名（以空格分隔）。

供 start.sh 调用：只安装缺失的依赖，避免每次都全量安装。
"""
import importlib
import sys
from pathlib import Path

# requirements.txt 包名 -> Python import 模块名 映射
# （仅处理 import 名与 pip 包名不一致的情况，其余直接同名转换）
IMPORT_MAP = {
    'fastapi': 'fastapi',
    'uvicorn': 'uvicorn',
    'sqlalchemy': 'sqlalchemy',
    'openpyxl': 'openpyxl',
    'passlib': 'passlib',
    'python-multipart': 'multipart',
}


def normalize_req(line: str):
    """从 requirements.txt 一行解析出纯包名，忽略版本和 extra 标记"""
    line = line.split('#')[0].strip()
    if not line:
        return None
    pkg = line.split('[')[0]          # 去掉 extra 标记，如 passlib[bcrypt] -> passlib
    for sep in ('>=', '==', '<=', '~=', '>', '<'):
        pkg = pkg.split(sep)[0]
    pkg = pkg.strip()
    return pkg or None


def main() -> int:
    req_file = Path(__file__).resolve().parent / 'requirements.txt'
    if not req_file.exists():
        print("[错误] 未找到 requirements.txt", file=sys.stderr)
        return 1

    missing = []
    for line in req_file.read_text(encoding='utf-8').splitlines():
        pkg = normalize_req(line)
        if not pkg:
            continue
        mod = IMPORT_MAP.get(pkg, pkg.replace('-', '_'))
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(pkg)

    print(' '.join(missing))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
