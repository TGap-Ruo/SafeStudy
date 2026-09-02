#!/usr/bin/env python3
"""
江苏安全平台 - 非交互式运行入口 (v1.0.7)
通过命令行参数传入学校、账号、密码，替代原 main.py 的交互式 input()。
用法: python safety_noncui.py --school "学校名称" --username 账号 --password 密码

同步上游 Scwizard/jiangsu-safety-platform-skip v1.0.7：
- 创建考试前动态获取当前有效考试 id（旧考试 id 已过期，会抽到旧题库）
- 课程完成 / 交卷需携带防作弊 token（由 create 响应 / unitTest/create 签发）
- 答题时间过短（code 1006）自动等待重试
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

# 防作弊：提交前的最短等待秒数
WAIT_SECONDS = 1

UNIT_TEST_URL = "http://wap.xiaoyuananquantong.com/guns-vip-main/wap/unitTest"
COMPULSORY_URL = "http://wap.xiaoyuananquantong.com/guns-vip-main/wap/compulsory/list"


def _load_json(text: str) -> dict:
    """安全解析平台 JSON 响应。"""
    try:
        res = json.loads(text)
        if not isinstance(res, dict):
            raise TypeError("响应不是 JSON 对象")
        return res
    except (json.JSONDecodeError, TypeError) as e:
        print(f"[错误] 平台返回非 JSON 响应（可能登录失效或平台变更）: {e}", flush=True)
        print(f"[错误] 原始响应: {text[:500]}", flush=True)
        sys.exit(1)


def _check_data_dict(res: dict, step: str) -> dict:
    """校验响应中的 data 字段为字典，否则打印平台完整响应并退出。"""
    data = res.get("data")
    if not isinstance(data, dict):
        print(f"[错误] {step}未返回正常结果，平台响应: {json.dumps(res, ensure_ascii=False)}", flush=True)
        print("[提示] 常见原因：课程未全部完成 / 考试次数已用完 / 登录状态失效 / 平台接口变更", flush=True)
        sys.exit(1)
    return data


def find_school_id(school_keyword: str) -> str:
    """根据学校名称关键词查找 collegeId，精准匹配优先，否则取第一个匹配。"""
    try:
        school_list = _load_json(utils.getAllSchools("江苏省"))
    except SystemExit:
        print("[错误] 获取学校列表失败", flush=True)
        sys.exit(1)

    school_data = school_list.get("data")
    if not isinstance(school_data, list):
        print(f"[错误] 学校列表未返回正常结果，平台响应: {json.dumps(school_list, ensure_ascii=False)}", flush=True)
        sys.exit(1)
    matches = []
    for s in school_data:
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


def main():
    parser = argparse.ArgumentParser(description="江苏安全平台一键完成（非交互版）")
    parser.add_argument("--school", required=True, help="学校名称（支持关键词）")
    parser.add_argument("--username", required=True, help="账号")
    parser.add_argument("--password", required=True, help="密码")
    args = parser.parse_args()

    print("=" * 50, flush=True)
    print("江苏安全平台一键完成脚本 (v1.0.7 - 非交互版)", flush=True)
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

    # 3. 题库映射（与上游 main.py 一致）
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
    res = _load_json(utils.session.post(
        COMPULSORY_URL,
        data={"userId": user_id, "collegeId": college_id},
    ).text)
    course = res.get("data")
    if not isinstance(course, list):
        print(f"[错误] 课程列表未返回正常结果，平台响应: {json.dumps(res, ensure_ascii=False)}", flush=True)
        sys.exit(1)
    unfinished = []
    for idx, c in enumerate(course):
        status = "已完成" if c["isFinsh"] else "未完成"
        print(f"  第{idx + 1}课 {c['name']} {status}", flush=True)
        if not c["isFinsh"]:
            unfinished.append(idx)

    # 5. 完成未完成的课程（v1.0.7：需先签发防作弊会话 logId/token）
    if unfinished:
        for i in unfinished:
            print(f"[信息] 正在完成: {table[i]['title']}（签发防作弊会话，等待 {WAIT_SECONDS} 秒后提交）...", flush=True)
            sess = utils.createUnitSession(user_id, table[i]["articleId"])
            payload = dict(table[i])
            payload["logId"] = sess["logId"]
            payload["token"] = sess["token"]
            time.sleep(WAIT_SECONDS)
            utils.session.post(UNIT_TEST_URL, data=payload).text
        print("[信息] 课程学习完成，复查完成度:", flush=True)
        res = _load_json(utils.session.post(
            COMPULSORY_URL,
            data={"userId": user_id, "collegeId": college_id},
        ).text)
        course = res.get("data")
        if not isinstance(course, list):
            print(f"[错误] 复查课程列表失败，平台响应: {json.dumps(res, ensure_ascii=False)}", flush=True)
            sys.exit(1)
        for idx, c in enumerate(course):
            status = "已完成" if c["isFinsh"] else "未完成"
            print(f"  第{idx + 1}课 {c['name']} {status}", flush=True)
    else:
        print("[信息] 所有课程已完成，直接进入考试", flush=True)

    # 6. 考试流程
    print("[信息] 正在进入考试流程...", flush=True)
    try:
        res = utils.creatExam(user_id)
    except Exception as e:
        print(f"[错误] 创建考试异常: {e}", flush=True)
        print("[提示] 若课程未全部完成或平台更新，请前往 github.com/Scwizard/jiangsu-safety-platform-skip 下载新版", flush=True)
        sys.exit(1)
    data = _check_data_dict(res, "创建考试")
    log_id = data.get("logId")
    token = data.get("token", "")  # v1.0.7：提交凭证（防作弊），create 响应里带
    if not log_id:
        print(f"[错误] 创建考试未返回 logId，平台响应: {json.dumps(res, ensure_ascii=False)}", flush=True)
        sys.exit(1)
    print(f"[信息] 取得 logId: {log_id}", flush=True)

    exam_list = utils.getExam(logId=log_id, userId=user_id)
    exam_data = _check_data_dict(exam_list, "获取考题")
    questions = exam_data.get("data")
    if not isinstance(questions, list) or not questions:
        print(f"[错误] 未取得考题列表，平台响应: {json.dumps(exam_list, ensure_ascii=False)}", flush=True)
        sys.exit(1)
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

    # 7. 提交考试（v1.0.7：携带 token；答题时间过短 code=1006 自动重试）
    print(f"[信息] 答案已生成，等待最短答题时长 {WAIT_SECONDS} 秒后提交（防作弊校验）...", flush=True)
    time.sleep(WAIT_SECONDS)

    def do_submit() -> dict:
        return _load_json(utils.imitateExam(exam_id, log_id, user_id, answers, token).text)

    res = do_submit()
    for _ in range(6):
        if res.get("code") == 1006:  # 答题时间过短
            print("[提示] 答题时间过短（code 1006），等待 10 秒后重试...", flush=True)
            time.sleep(10)
            res = do_submit()
            continue
        break

    data = _check_data_dict(res, "提交考试")
    score = data.get("count")
    if score is None:
        print(f"[错误] 提交考试未返回得分，平台响应: {json.dumps(res, ensure_ascii=False)}", flush=True)
        sys.exit(1)
    score = int(score)
    print(f"[结果] 得分: {score}", flush=True)

    if score != 100:
        print("[提示] 未到100分，可重新运行一次（题库历史遗留问题）", flush=True)
    else:
        print(f"[结果] 满分！结课证书: http://wap.xiaoyuananquantong.com/guns-vip-main/wap/qrCode?userId={user_id}", flush=True)

    # 8. 解绑退出
    print("[信息] 正在解绑并退出登录...", flush=True)
    res = utils.UntyingMethod(user_id)
    print(f"[信息] 解绑结果: {res}", flush=True)

    elapsed = time.time() - start_time
    print(f"[信息] 执行耗时: {elapsed:.3f} 秒", flush=True)
    print("=" * 50, flush=True)
    print("执行完成", flush=True)


if __name__ == "__main__":
    main()
