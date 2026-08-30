"""命令行入口。"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def cmd_clean() -> int:
    """清空工作区垃圾：inbox/ 全部内容 + workspace/ 下所有任务目录。"""
    root = _repo_root()
    inbox = root / "inbox"
    ws = root / "workspace"
    removed = 0

    if inbox.exists():
        for f in inbox.iterdir():
            if f.is_dir():
                shutil.rmtree(f)
            else:
                f.unlink()
            removed += 1
    if ws.exists():
        for d in ws.iterdir():
            if d.name == ".gitkeep":
                continue
            if d.is_dir():
                shutil.rmtree(d)
            else:
                d.unlink()
            removed += 1

    print(f"已清理 {removed} 项：inbox/ 与 workspace/ 下的所有任务文件。")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xiumi", description="秀米排版小助手")
    parser.add_argument("command", nargs="?", default="chat",
                        help="chat 启动对话（默认）；clean 清空 inbox 与 workspace 任务文件")
    args = parser.parse_args(argv)
    if args.command == "chat":
        from .chat.tui import run_tui
        run_tui()
        return 0
    if args.command == "clean":
        return cmd_clean()
    parser.error(f"未知命令：{args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
