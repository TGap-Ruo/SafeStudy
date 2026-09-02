#!/usr/bin/env python3
"""
江苏安全平台 - 非交互式运行入口
通过命令行参数传入学校、账号、密码，替代原 main.py 的交互式 input()。
用法: python safety_noncui.py --school "学校名称" --username 账号 --password 密码
"""
import argparse
import json
import os
import sys
import time

import utils

# 关闭脚本用量统计（Web 服务环境下不需要）
STATS = False

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)


def find_school_id(school_keyword: str) -> str:
    """根据学校名称关键词查找 collegeId，精准匹配优先，否则取第一个匹配。"""
    try:
        school_list = json.loads(utils.getAllSchools("江苏省"))
    except Exception as e:
        print(f"[错误] 获取学校列表失败: {e}", flush=True)
        sys.exit(1)

    matches = []
    for s in school_list.get("data", []):
        if school_keyword in s["name"]:
            matches.append(s)

    if not matches:
        print(f"[错误] 未找到包含 '{school_keyword}' 的学校", flush=True)
        sys.exit(1)

    # 精准匹配优先
    for s in matches:
        if s["name"] == school_keyword:
            print(f"[信息] 已匹配学校: {s['name']} (id: {s['id']})", flush=True)
            return s["id"]

    # 否则取第一个
    s = matches[0]
    print(f"[信息] 模糊匹配学校: {s['name']} (id: {s['id']})", flush=True)
    return s["id"]


def get_submit_score(resp_text: str) -> int:
    """解析提交考试接口的响应，返回得分。

    平台异常时 data 字段可能不是字典（例如返回错误提示字符串），
    这里统一校验并打印平台完整响应，避免裸 TypeError。
    """
    try:
        res = json.loads(resp_text)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"[错误] 提交考试返回非 JSON 响应（可能登录失效或平台变更）: {e}", flush=True)
        print(f"[错误] 原始响应: {resp_text[:500]}", flush=True)
        sys.exit(1)

    data = res.get("data")
    if not isinstance(data, dict) or "count" not in data:
        print(f"[错误] 提交考试未返回得分，平台响应: {json.dumps(res, ensure_ascii=False)}", flush=True)
        print("[提示] 常见原因：考试次数已用完 / 尚未完成全部课程 / 登录状态失效 / 平台接口变更", flush=True)
        sys.exit(1)
    return int(data["count"])


def main():
    parser = argparse.ArgumentParser(description="江苏安全平台一键完成（非交互版）")
    parser.add_argument("--school", required=True, help="学校名称（支持关键词）")
    parser.add_argument("--username", required=True, help="账号")
    parser.add_argument("--password", required=True, help="密码")
    args = parser.parse_args()

    print("=" * 50, flush=True)
    print("江苏安全平台一键完成脚本 (v1.0.6 - 非交互版)", flush=True)
    print(f"学校: {args.school}", flush=True)
    print(f"账号: {args.username}", flush=True)
    print("=" * 50, flush=True)

    # 1. 获取学校 ID
    college_id = find_school_id(args.school)

    # 2. 登录
    print("[信息] 正在登录...", flush=True)
    login_result = utils.loginMethod(args.username, args.password, college_id)
    if not login_result.get("success"):
        print(f"[错误] 登录失败: {login_result}", flush=True)
        sys.exit(1)

    open_id = login_result["data"]["openId"]
    user_id = login_result["data"]["userId"]
    print(f"[信息] 登录成功，userId: {user_id}", flush=True)

    start_time = time.time()

    # 3. 题库映射（与原 main.py 一致）
    tiku1 = {"articleId": "2080135073788600321", "title": "题库学习", "userId": user_id, "ah": "", "question": "2080136617019842561-1", "quesType": "3"}
    tiku2 = {"articleId": "2079132357549375490", "title": "入学安全", "userId": user_id, "ah": "", "question": "2079154657984266242-1", "quesType": "3"}
    tiku3 = {"articleId": "2079133938168643585", "title": "国家安全", "userId": user_id, "ah": "", "question": "2079156723934838786-B", "quesType": "1"}
    tiku4 = {"articleId": "2079139032318623745", "title": "财物安全", "userId": user_id, "ah": "", "question": "2079446660177477633-1", "quesType": "3"}
    tiku5 = {"articleId": "2079140991327027201", "title": "心理健康", "userId": user_id, "ah": "", "question": "2079467760328392705-D", "quesType": "1"}
    tiku6 = {"articleId": "2079142411614830593", "title": "消防安全", "userId": user_id, "ah": "", "question": "2079492272201678850-C", "quesType": "1"}
    tiku7 = {"articleId": "2079143452481699842", "title": "人身安全", "userId": user_id, "ah": "", "question": "2079527272678703105-1", "quesType": "3"}
    tiku8 = {"articleId": "2079144978977669121", "title": "交通安全", "userId": user_id, "ah": "", "question": "2079540470853156866-A", "quesType": "1"}
    tiku9 = {"articleId": "2079146093836255234", "title": "禁毒防艾", "userId": user_id, "ah": "", "question": "2079548501443756034-1", "quesType": "3"}
    tiku10 = {"articleId": "2079146628521934850", "title": "应急救护", "userId": user_id, "ah": "", "question": "~2079553855799967746-A~2079553855799967746-B~2079553855799967746-C~2079553855799967746-D", "quesType": "2"}
    tiku11 = {"articleId": "2079147344531570690", "title": "防灾减灾", "userId": user_id, "ah": "", "question": "2079558043292418049-D", "quesType": "1"}
    table = {0: tiku1, 1: tiku2, 2: tiku3, 3: tiku4, 4: tiku5, 5: tiku6, 6: tiku7, 7: tiku8, 8: tiku9, 9: tiku10, 10: tiku11}

    # 4. 查询课程完成度
    print("[信息] 正在查询课程完成度...", flush=True)
    res = utils.session.post(
        "http://wap.xiaoyuananquantong.com/guns-vip-main/wap/compulsory/list",
        data={"userId": user_id, "collegeId": college_id},
    ).text
    data = json.loads(res)
    course = data["data"]
    unfinished = []
    for idx, c in enumerate(course):
        status = "已完成" if c["isFinsh"] else "未完成"
        print(f"  第{idx + 1}课 {c['name']} {status}", flush=True)
        if not c["isFinsh"]:
            unfinished.append(idx)

    # 5. 完成未完成的课程
    if unfinished:
        for i in unfinished:
            print(f"[信息] 正在完成: {table[i]['title']}", flush=True)
            utils.session.post(
                "http://wap.xiaoyuananquantong.com/guns-vip-main/wap/unitTest",
                data=table[i],
            ).text
        print("[信息] 课程学习完成，复查完成度:", flush=True)
        res = utils.session.post(
            "http://wap.xiaoyuananquantong.com/guns-vip-main/wap/compulsory/list",
            data={"userId": user_id, "collegeId": college_id},
        ).text
        data = json.loads(res)
        for idx, c in enumerate(data["data"]):
            status = "已完成" if c["isFinsh"] else "未完成"
            print(f"  第{idx + 1}课 {c['name']} {status}", flush=True)
    else:
        print("[信息] 所有课程已完成，直接进入考试", flush=True)

    # 6. 考试流程
    print("[信息] 正在进入考试流程...", flush=True)
    res = utils.creatExam(user_id)
    log_id = res["data"]["logId"]
    print(f"[信息] 取得 logId: {log_id}", flush=True)

    exam_list = utils.getExam(logId=log_id, userId=user_id)
    questions = exam_list["data"]["data"]
    print("[信息] 取得考题列表，正在从数据库读取答案...", flush=True)

    data = utils.getExamId(user_id)
    if data.get("code") == 500:
        print("[错误] 账号未完成内容学习或平台更新，无法考试", flush=True)
        sys.exit(1)

    exam_id = data["data"]["id"]
    question_list = [questions[i]["questionId"] for i in range(min(50, len(questions)))]

    answers = ()
    for qid in question_list:
        try:
            answers += utils.getAnswerById(qid)
        except Exception as e:
            print(f"[错误] 数据库读写错误: {e}", flush=True)
            sys.exit(1)

    print("[信息] 答案已生成，正在提交考试...", flush=True)
    res = utils.imitateExam(exam_id, log_id, user_id, answers)
    score = get_submit_score(res.text)
    print(f"[结果] 得分: {score}", flush=True)

    if score != 100:
        print("[提示] 未到100分，可重新运行一次（题库历史遗留问题）", flush=True)
    else:
        print(f"[结果] 满分！结课证书: http://wap.xiaoyuananquantong.com/guns-vip-main/wap/qrCode?userId={user_id}", flush=True)

    # 7. 解绑退出
    print("[信息] 正在解绑并退出登录...", flush=True)
    res = utils.UntyingMethod(user_id)
    print(f"[信息] 解绑结果: {res}", flush=True)

    elapsed = time.time() - start_time
    print(f"[信息] 执行耗时: {elapsed:.3f} 秒", flush=True)
    print("=" * 50, flush=True)
    print("执行完成", flush=True)


if __name__ == "__main__":
    main()
