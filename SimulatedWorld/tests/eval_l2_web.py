#!/usr/bin/env python3
"""
L2 Web Agent 网页操作能力测试 — 评分脚本
使用 LLM 对比 Agent 回答与标准答案，输出分维度评分报告

用法:
  python3 eval_l2_web.py                        # 评估所有 L2 Web 用例
  python3 eval_l2_web.py --case l2_web_t1        # 只评估单个
  python3 eval_l2_web.py --run-first              # 先截图+跑GA再评估
"""

import os, sys, json, time, subprocess, argparse, re
from pathlib import Path

# 将 GenericAgent 加入 path
GA_DIR = "/mnt/d/work/Hackthon/GenericAgent"
sys.path.insert(0, GA_DIR)

# 确保可以 import 同目录下的标准答案
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from l2_web_standard_answers import STANDARD_ANSWERS


# ─── LLM 调用（复用 GenericAgent 的 NativeOAISession） ───

def load_eval_llm():
    """从 GenericAgent 的 mykey 中加载 LLM"""
    sys.path.insert(0, GA_DIR)
    from llmcore import reload_mykeys
    keys, _ = reload_mykeys()

    for k, cfg in keys.items():
        if 'native_oai' in k and isinstance(cfg, dict):
            from llmcore import NativeOAISession
            sess = NativeOAISession(cfg)
            print(f"[Eval] 使用 LLM: {sess.model} (via {k})")
            return sess

    for k, cfg in keys.items():
        if 'mixin' in k and isinstance(cfg, dict):
            from llmcore import MixinSession, NativeToolClient
            all_sessions = []
            for k2, cfg2 in keys.items():
                if not any(x in k2 for x in ['api', 'config', 'cookie']):
                    continue
                if 'mixin' in k2:
                    continue
                from llmcore import resolve_client
                c = resolve_client(k2)
                if c:
                    all_sessions.append(c)
            mixin = MixinSession(all_sessions, cfg)
            print(f"[Eval] 使用 LLM: MixinSession")
            return mixin._sessions[0]

    raise RuntimeError("未找到可用的 LLM 配置，请检查 mykey.py")


def exhaust(g):
    """消费生成器，返回 StopIteration 的 value"""
    try:
        while True:
            next(g)
    except StopIteration as e:
        return e.value


def ask_llm(sess, prompt: str) -> str:
    """向 LLM 发送 prompt，返回完整文本回复"""
    from llmcore import _fix_messages
    messages = _fix_messages([{"role": "user", "content": prompt}])
    gen = sess.raw_ask(messages)
    result = exhaust(gen)

    if isinstance(result, list):
        texts = []
        for block in result:
            if isinstance(block, dict) and block.get('type') == 'text':
                texts.append(block.get('text', ''))
            elif isinstance(block, str):
                texts.append(block)
        return '\n'.join(texts)
    if isinstance(result, str):
        return result
    if hasattr(result, 'content'):
        content = result.content
        if isinstance(content, list):
            return '\n'.join(b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text')
        return str(content)
    return str(result)


def build_eval_prompt(case_id: str, case_def: dict, agent_output: str) -> str:
    """构造评分 prompt"""
    dimensions = case_def["dimensions"]

    dim_text = ""
    for dim_id, dim_def in dimensions.items():
        dim_text += f"""
### {dim_def['label']}（权重 {dim_def['weight']}分）
**标准答案要点：**
{dim_def['criteria']}
"""

    prompt = f"""你是一位严格的游戏AI评测官，专门评估 Agent 在网页操作任务中的表现。请对比以下 Agent 的回答与标准答案，对每个维度评分。

## 任务信息
- 任务ID：{case_id}
- 任务名称：{case_def['name']}
- 任务类型：{case_def.get('task_type', 'B-网页任务')}
- 难度：{case_def.get('difficulty', '未知')}

## 标准答案（按维度）
{dim_text}

## Agent 的回答
```
{agent_output[:8000]}
```

## 评分要求
请对每个维度给出：
1. **得分**（0到该维度满分），精确到整数
2. **扣分原因**（如果扣分，具体说明哪里不对/不完整/理解错误）
3. **亮点**（如果回答中有超出标准答案的亮点或特别好的分析）

特别提醒：
- 网页任务的核心考察点是视觉理解（OCR/VLM 解析截图）和约束推理
- 如果 Agent 没有解析截图就给答案（盲猜），在视觉理解维度应大幅扣分
- 如果 Agent 把"射程"当成"攻击力"，在目标理解维度应扣分

最后给出总分和综合评价（一句话）。

请严格按以下 JSON 格式输出评分结果（不要包含其他内容）：
```json
{{
  "dimensions": {{
    "{list(dimensions.keys())[0]}": {{"score": N, "max": {dimensions[list(dimensions.keys())[0]]['weight']}, "deduction": "扣分原因或空", "highlight": "亮点或空"}},
    ...
  }},
  "total_score": N,
  "total_max": 100,
  "verdict": "综合评价一句话"
}}
```
"""
    return prompt


def parse_score_json(text: str) -> dict:
    """从 LLM 回复中提取 JSON 评分"""
    m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if m:
        try:
            return json.loads(m.group(1))
        except:
            pass

    m = re.search(r'\{[\s\S]*"total_score"[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except:
            pass

    return {"error": "无法解析评分JSON", "raw": text[:500]}


def read_agent_output(case_id: str) -> str:
    """读取 Agent 输出，提取正文（去掉工具调用噪音）"""
    output_path = os.path.join(GA_DIR, "temp", case_id, "output.txt")
    if not os.path.exists(output_path):
        return f"[ERROR] 输出文件不存在: {output_path}"

    with open(output_path, "r", encoding="utf-8") as f:
        raw = f.read()

    lines = raw.split("\n")
    cleaned = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("🛠️"):
            continue
        if stripped in ("`````", "````", "````text"):
            continue
        if stripped.startswith("[Info]") or stripped.startswith("[Status]"):
            continue
        if not stripped:
            continue
        cleaned.append(line)

    text = "\n".join(cleaned).strip()

    first_content = re.search(r'(## |一、|核心目标|任务目标|截图|视觉)', text)
    if first_content:
        text = text[first_content.start():]

    if len(text) > 10000:
        text = text[:10000] + "\n\n... [内容过长已截断]"

    return text


def run_single_test(case_id: str) -> bool:
    """运行单个 GA 测试用例"""
    task_dir = os.path.join(GA_DIR, "temp", case_id)
    input_file = os.path.join(task_dir, "input.txt")

    if not os.path.exists(input_file):
        print(f"  ❌ {case_id}: input.txt 不存在")
        return False

    # 清理旧输出
    import glob
    for f in glob.glob(os.path.join(task_dir, "output*.txt")):
        os.remove(f)
    for f in glob.glob(os.path.join(task_dir, "stdout.log")):
        os.remove(f)
    for f in glob.glob(os.path.join(task_dir, "stderr.log")):
        os.remove(f)

    print(f"  🏃 运行 {case_id} ...", end=" ", flush=True)

    try:
        result = subprocess.run(
            [sys.executable, os.path.join(GA_DIR, "agentmain.py"),
             "--task", case_id, "--nobg"],
            cwd=GA_DIR,
            capture_output=True,
            timeout=600,  # 网页任务可能更耗时（需要解析多张截图）
            env={**os.environ, "PYTHONPATH": GA_DIR}
        )

        output_file = os.path.join(task_dir, "output.txt")
        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            print(f"✅ ({size} bytes)")
            return True
        else:
            # 检查 output0.txt
            output0 = os.path.join(task_dir, "output0.txt")
            if os.path.exists(output0):
                import shutil
                shutil.copy(output0, output_file)
                print(f"✅ (output0 → output.txt)")
                return True
            print(f"❌ 无输出文件 (exit={result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏰ 超时 (600s)")
        return False
    except Exception as e:
        print(f"❌ {e}")
        return False


def evaluate_case(sess, case_id: str) -> dict:
    """评估单个用例"""
    case_def = STANDARD_ANSWERS[case_id]
    agent_output = read_agent_output(case_id)

    if agent_output.startswith("[ERROR]"):
        return {"error": agent_output, "case_id": case_id}

    print(f"  📝 评估 {case_def['name'][:30]} ...", end=" ", flush=True)

    prompt = build_eval_prompt(case_id, case_def, agent_output)

    try:
        response = ask_llm(sess, prompt)
        result = parse_score_json(response)
        result["case_id"] = case_id
        result["case_name"] = case_def["name"]
        result["difficulty"] = case_def.get("difficulty", "?")
        print(f"✅ (总分: {result.get('total_score', '?')}/{result.get('total_max', 100)})")
        return result
    except Exception as e:
        print(f"❌ {e}")
        return {"error": str(e), "case_id": case_id}


def print_report(results: list):
    """打印评分报告"""
    print("\n" + "=" * 70)
    print("  L2 Web Agent 网页操作能力 — 评分报告")
    print("=" * 70)

    grand_total = 0
    grand_max = 0

    for r in results:
        if "error" in r:
            print(f"\n  ❌ {r['case_id']}: {r['error']}")
            continue

        difficulty = r.get('difficulty', '?')
        print(f"\n── {r['case_name']} ({r['case_id']}) [难度:{difficulty}] ──")

        dims = r.get("dimensions", {})
        for dim_id, dim_result in dims.items():
            score = dim_result.get("score", 0)
            max_s = dim_result.get("max", 10)
            bar = "█" * score + "░" * (max_s - score)
            print(f"  {dim_id:25s} {bar} {score}/{max_s}")
            if dim_result.get("deduction"):
                print(f"    ⚠️  {dim_result['deduction']}")
            if dim_result.get("highlight"):
                print(f"    💡 {dim_result['highlight']}")

        ts = r.get("total_score", 0)
        tm = r.get("total_max", 100)
        print(f"  {'总计':25s} {ts}/{tm}")
        print(f"  📋 {r.get('verdict', 'N/A')}")

        grand_total += ts
        grand_max += tm

    if grand_max > 0:
        avg = grand_total / grand_max * 100
        print(f"\n{'=' * 70}")
        print(f"  综合得分: {grand_total}/{grand_max} ({avg:.0f}%)")
        print(f"{'=' * 70}\n")

    # 按难度汇总
    print("  按难度统计:")
    diff_scores = {}
    for r in results:
        if "error" in r:
            continue
        d = r.get('difficulty', '?')
        if d not in diff_scores:
            diff_scores[d] = []
        diff_scores[d].append(r.get('total_score', 0))
    for d in sorted(diff_scores.keys()):
        scores = diff_scores[d]
        print(f"    {d}: 平均 {sum(scores)/len(scores):.0f}/100")


def main():
    parser = argparse.ArgumentParser(description="L2 Web Agent 网页操作能力评测")
    parser.add_argument("--case", help="只评估指定用例 (l2_web_t1/t2/t5)")
    parser.add_argument("--run-first", action="store_true", help="先截图+运行测试再评估")
    parser.add_argument("--no-run", action="store_true", help="不运行测试，只评估已有输出")
    args = parser.parse_args()

    cases = [args.case] if args.case else list(STANDARD_ANSWERS.keys())

    # ─── Step 0: 截图（如果 --run-first） ───
    if args.run_first:
        print("\n📸 截取 WebUI 截图 ...")
        cap_script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "SimulatedWorld", "web_shop", "capture_screenshots.py"
        )
        for case_id in cases:
            task_dir = os.path.join(GA_DIR, "temp", case_id)
            subprocess.run([sys.executable, cap_script, "--task-dir", task_dir],
                           timeout=120)

    # ─── Step 1: 运行 GA 测试 ───
    if args.run_first and not args.no_run:
        print("\n🏃 运行 L2 Web 测试用例 ...\n")
        for case_id in cases:
            run_single_test(case_id)

    # ─── Step 2: 评估 ───
    print("\n🔍 加载 LLM 评测官 ...")
    sess = load_eval_llm()

    print("\n📊 开始评估 ...\n")
    results = []
    for case_id in cases:
        if case_id not in STANDARD_ANSWERS:
            print(f"  ⚠️ {case_id}: 无标准答案定义，跳过")
            continue
        result = evaluate_case(sess, case_id)
        results.append(result)

    # ─── Step 3: 打印报告 ───
    print_report(results)

    # 保存详细 JSON
    report_path = os.path.join(os.path.dirname(__file__), "l2_web_eval_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"详细报告已保存到: {report_path}")


if __name__ == "__main__":
    main()
