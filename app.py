#!/usr/bin/env python3
"""
WeBan Web 服务 - Flask 主应用
提供网页界面、任务管理 API、实时输出 SSE、日志下载。
"""
import os
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_file

import task_manager

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


@app.route("/")
def index():
    return render_template("index.html")


# ── 任务管理 API ──────────────────────────────────────────

@app.route("/api/tasks", methods=["GET"])
def api_list_tasks():
    """获取任务列表。"""
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"tasks": task_manager.list_tasks(limit)})


@app.route("/api/tasks", methods=["POST"])
def api_start_task():
    """启动新任务。"""
    data = request.get_json(force=True)
    program = data.get("program", "").strip()
    school = data.get("school", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if program not in ("weban", "safety"):
        return jsonify({"error": "请选择程序类型"}), 400
    if not school:
        return jsonify({"error": "请输入学校名称"}), 400
    if not username:
        return jsonify({"error": "请输入账号"}), 400
    if not password:
        return jsonify({"error": "请输入密码"}), 400

    task_id = task_manager.start_task(program, school, username, password)
    return jsonify({"id": task_id, "status": "running"})


@app.route("/api/tasks/<task_id>", methods=["GET"])
def api_get_task(task_id):
    """获取任务详情。"""
    t = task_manager.get_task(task_id)
    if not t:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(t)


@app.route("/api/tasks/<task_id>/stop", methods=["POST"])
def api_stop_task(task_id):
    """停止任务。"""
    ok, msg = task_manager.stop_task(task_id)
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"status": "stopped", "message": msg})


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def api_delete_task(task_id):
    """删除任务。"""
    ok, msg = task_manager.delete_task(task_id)
    if not ok:
        return jsonify({"error": msg}), 400
    return jsonify({"status": "deleted", "message": msg})


@app.route("/api/tasks/<task_id>/output", methods=["GET"])
def api_task_output(task_id):
    """获取任务输出（从指定行开始）。"""
    start_line = request.args.get("from", 0, type=int)
    output, total_lines = task_manager.get_task_output(task_id, start_line)
    return jsonify({
        "output": output,
        "total_lines": total_lines,
        "from": start_line,
    })


@app.route("/api/tasks/<task_id>/log", methods=["GET"])
def api_download_log(task_id):
    """下载任务日志文件。"""
    log_path = task_manager.get_log_file_path(task_id)
    if not log_path or not os.path.exists(log_path):
        return jsonify({"error": "日志文件不存在"}), 404
    t = task_manager.get_task(task_id)
    filename = f"{t['program']}_{t['username']}_{task_id}.log"
    return send_file(log_path, as_attachment=True, download_name=filename)


# ── SSE 实时输出 ──────────────────────────────────────────

@app.route("/api/stream/<task_id>")
def stream(task_id):
    """SSE 实时推送任务输出。"""
    def generate():
        last_line = 0
        # 先发送已有输出
        output, total = task_manager.get_task_output(task_id, 0)
        if output:
            yield f"data: {_sse_encode(output)}\n\n"
            last_line = total

        # 持续推送新输出
        while True:
            t = task_manager.get_task(task_id)
            if not t:
                yield "event: error\ndata: 任务不存在\n\n"
                break
            output, total = task_manager.get_task_output(task_id, last_line)
            if output:
                yield f"data: {_sse_encode(output)}\n\n"
                last_line = total
            if t.get("status") in ("finished", "failed", "stopped"):
                # 任务结束，再读一次确保拿到所有输出
                output, total = task_manager.get_task_output(task_id, last_line)
                if output:
                    yield f"data: {_sse_encode(output)}\n\n"
                yield f"event: end\ndata: {t['status']}\n\n"
                break
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


def _sse_encode(text):
    """将文本编码为 SSE 数据格式（处理换行）。"""
    return text.replace("\n", "\\n").replace("\r", "")


# ── 健康检查 ──────────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
