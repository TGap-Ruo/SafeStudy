#!/usr/bin/env python3
"""
任务管理器：负责子进程的启动、输出捕获、状态管理、日志持久化。
每个任务独立进程，支持多开。
"""
import json
import os
import subprocess
import threading
import time
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
TASKS_FILE = BASE_DIR / "tasks.json"
PROGRAMS_DIR = BASE_DIR / "programs"

# Google Chrome 可执行文件路径（使用系统安装的 Chrome，无需 playwright 下载浏览器）
# 可通过环境变量 WEBBAN_CHROME_PATH 覆盖
CHROME_PATH = os.environ.get("WEBBAN_CHROME_PATH", "/usr/bin/google-chrome-stable")

# CDP 远程浏览器（可选）。当 WEBBAN_CDP_HOST 与 WEBBAN_CDP_PORT 同时设置时，
# WeBan 不再自己启动 Chrome，而是连接这里指定的 CDP 实例。
# 适用场景：服务以 root 运行（宝塔面板/systemd User=root）或容器内直接启动
# Chrome 会因沙箱失败，需要先用 --no-sandbox 单独启动一个 Chrome CDP 实例
# （参见 cdp-chrome.sh），再由任务连接它。
CDP_HOST = os.environ.get("WEBBAN_CDP_HOST", "").strip()
_CDP_PORT_RAW = os.environ.get("WEBBAN_CDP_PORT", "").strip()
try:
    CDP_PORT = int(_CDP_PORT_RAW) if _CDP_PORT_RAW else 0
except ValueError:
    CDP_PORT = 0

# WeBan 二进制可执行文件路径（仅使用编译好的二进制，不使用 Python 源码）
WEBBAN_BINARY_PATH = PROGRAMS_DIR / "weban" / "WeBan-linux-x64"

LOGS_DIR.mkdir(exist_ok=True)

# 内存中的任务状态
tasks = {}
# 每个任务的输出缓冲区（最近 N 行，用于 SSE 实时推送）
output_buffers = {}
# 每个任务的完整输出（用于历史查看）
MAX_BUFFER_LINES = 2000


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_tasks():
    """从 tasks.json 加载历史任务记录。"""
    if TASKS_FILE.exists():
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 重启后，之前 running 的任务标记为 unknown（进程已不存在）
            for tid, t in data.items():
                if t.get("status") == "running":
                    t["status"] = "stopped"
                    t["stop_reason"] = "服务重启"
                tasks[tid] = t
        except (json.JSONDecodeError, OSError):
            pass


def _save_tasks():
    """持久化任务记录到 tasks.json。"""
    try:
        # 只保存元数据，不保存输出缓冲区
        serializable = {}
        for tid, t in tasks.items():
            serializable[tid] = {k: v for k, v in t.items() if k not in ("process", "log_fp")}
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def list_tasks(limit=50):
    """返回任务列表，按创建时间倒序。"""
    result = []
    for tid, t in sorted(tasks.items(), key=lambda x: x[1].get("created_at", ""), reverse=True):
        result.append({
            "id": tid,
            "program": t.get("program"),
            "school": t.get("school"),
            "username": t.get("username"),
            "status": t.get("status"),
            "created_at": t.get("created_at"),
            "finished_at": t.get("finished_at"),
            "exit_code": t.get("exit_code"),
            "stop_reason": t.get("stop_reason", ""),
        })
    return result[:limit]


def get_task(task_id):
    """获取单个任务详情。"""
    t = tasks.get(task_id)
    if not t:
        return None
    return {
        "id": task_id,
        "program": t.get("program"),
        "school": t.get("school"),
        "username": t.get("username"),
        "status": t.get("status"),
        "created_at": t.get("created_at"),
        "finished_at": t.get("finished_at"),
        "exit_code": t.get("exit_code"),
        "stop_reason": t.get("stop_reason", ""),
        "log_file": t.get("log_file"),
    }


def get_task_output(task_id, start_line=0):
    """获取任务输出，从指定行开始。"""
    buf = output_buffers.get(task_id)
    if buf is None:
        # 尝试从日志文件读取
        t = tasks.get(task_id)
        if t and t.get("log_file") and os.path.exists(t["log_file"]):
            try:
                with open(t["log_file"], "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                return "".join(lines[start_line:]), len(lines)
            except OSError:
                pass
        return "", 0
    lines = list(buf)
    return "".join(lines[start_line:]), len(lines)


def _build_command(program, school, username, password, task_id):
    """根据程序类型构建启动命令和工作目录。"""
    data_dir = LOGS_DIR / task_id
    data_dir.mkdir(exist_ok=True)

    if program == "weban":
        weban_dir = PROGRAMS_DIR / "weban"
        # 使用编译好的二进制可执行文件
        cmd = [
            str(WEBBAN_BINARY_PATH),
            "--tenant-name", school,
            "--username", username,
            "--password", password,
            "--non-interactive",
            "--data-dir", str(data_dir),
            "--study-mode", "true",
            "--exam-mode", "perfect",
        ]
        if CDP_HOST and CDP_PORT:
            # CDP 模式：连接外部 --no-sandbox 启动的 Chrome，避免 root 沙箱问题
            cmd += ["--cdp-host", CDP_HOST, "--cdp-port", str(CDP_PORT)]
        else:
            # 本地模式：nodriver 直接启动 Chrome（需非 root 用户运行）
            cmd += ["--browser-path", CHROME_PATH]
        return cmd, str(weban_dir)
    elif program == "safety":
        safety_dir = PROGRAMS_DIR / "safety"
        cmd = [
            "python3",
            str(safety_dir / "safety_noncui.py"),
            "--school", school,
            "--username", username,
            "--password", password,
        ]
        return cmd, str(safety_dir)
    else:
        raise ValueError(f"未知程序类型: {program}")


import sys  # noqa: E402  (放在这里避免循环引用问题)


def start_task(program, school, username, password):
    """启动一个新任务。"""
    task_id = uuid.uuid4().hex[:12]
    log_file = str(LOGS_DIR / task_id / "run.log")

    cmd, cwd = _build_command(program, school, username, password, task_id)

    # 打开日志文件
    log_fp = open(log_file, "w", encoding="utf-8", buffering=1)

    # 启动子进程
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONUNBUFFERED": "1", "ENVIRONMENT": "docker"},
    )

    task_info = {
        "id": task_id,
        "program": program,
        "school": school,
        "username": username,
        "status": "running",
        "created_at": _now_str(),
        "finished_at": None,
        "exit_code": None,
        "log_file": log_file,
        "process": proc,
        "log_fp": log_fp,
        "stop_reason": "",
    }
    tasks[task_id] = task_info
    output_buffers[task_id] = deque(maxlen=MAX_BUFFER_LINES)

    # 启动输出读取线程
    threading.Thread(
        target=_read_output,
        args=(task_id, proc, log_fp),
        daemon=True,
    ).start()

    _save_tasks()
    return task_id


def _read_output(task_id, proc, log_fp):
    """后台线程：实时读取子进程输出，写入缓冲区和日志文件。"""
    buf = output_buffers.get(task_id)
    try:
        for line in proc.stdout:
            if buf is not None:
                buf.append(line)
            log_fp.write(line)
            log_fp.flush()
    except (ValueError, OSError):
        pass
    finally:
        proc.wait()
        log_fp.close()
        # 更新任务状态
        t = tasks.get(task_id)
        if t:
            t["status"] = "finished" if proc.returncode == 0 else "failed"
            t["exit_code"] = proc.returncode
            t["finished_at"] = _now_str()
            if "process" in t:
                del t["process"]
            if "log_fp" in t:
                del t["log_fp"]
        _save_tasks()


def stop_task(task_id):
    """停止一个运行中的任务。"""
    t = tasks.get(task_id)
    if not t:
        return False, "任务不存在"
    if t.get("status") != "running":
        return False, "任务未在运行"
    proc = t.get("process")
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        t["status"] = "stopped"
        t["finished_at"] = _now_str()
        t["exit_code"] = proc.returncode
        t["stop_reason"] = "用户手动停止"
        if "process" in t:
            del t["process"]
        _save_tasks()
        return True, "已停止"
    return False, "进程不存在"


def delete_task(task_id):
    """删除任务记录及其日志。"""
    t = tasks.get(task_id)
    if not t:
        return False, "任务不存在"
    if t.get("status") == "running":
        return False, "任务正在运行，请先停止"
    # 删除日志目录
    log_dir = LOGS_DIR / task_id
    if log_dir.exists():
        import shutil
        shutil.rmtree(log_dir, ignore_errors=True)
    del tasks[task_id]
    if task_id in output_buffers:
        del output_buffers[task_id]
    _save_tasks()
    return True, "已删除"


def get_log_file_path(task_id):
    """获取任务日志文件路径。"""
    t = tasks.get(task_id)
    if t and t.get("log_file"):
        return t["log_file"]
    return None


# 初始化时加载历史任务
_load_tasks()
