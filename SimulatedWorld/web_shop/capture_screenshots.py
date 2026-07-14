#!/usr/bin/env python3
"""
截图捕获脚本 — 每次运行前启动 Flask，用 Playwright 截取所有页面截图
用法:
  python3 capture_screenshots.py                          # 默认端口 5090
  python3 capture_screenshots.py --port 5091             # 自定义端口
  python3 capture_screenshots.py --task-dir /path/to/ga/temp/l2_web_t1  # 同时复制到任务目录
"""

import subprocess, sys, os, time, argparse, glob, shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_DIR = os.path.join(SCRIPT_DIR, "screenshots")

# 需要截图的页面（使用 OCR 高对比度主题）
PAGES = {
    # T1 / T2 — 主页（所有信息可见）
    "t1_main": "/shop/t1?theme=ocr",
    "t2_main": "/shop/t2?theme=ocr",
    # T5 — 主页（信息隐藏）+ 5 个子页面
    "t5_main":    "/shop/t5?theme=ocr",
    "t5_weapons": "/specs/weapons?theme=ocr",
    "t5_defense": "/specs/defense?theme=ocr",
    "t5_utility": "/specs/utility?theme=ocr",
    "t5_rules":   "/rules?theme=ocr",
    "t5_intel":   "/intel?task=t5&theme=ocr",
}

WORKER_JS = os.path.join(SCRIPT_DIR, "screenshot_worker.js")


def capture(port: int, task_dir: str = None):
    """启动 Flask → 截图 → 复制到任务目录"""
    base_url = f"http://127.0.0.1:{port}"

    # 1. 启动 Flask
    app_path = os.path.join(SCRIPT_DIR, "app.py")
    flask_proc = subprocess.Popen(
        [sys.executable, app_path, "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(2)

    try:
        # 2. 确保截图目录存在
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)

        # 3. 准备 URL 列表 JSON
        import json
        urls = [{"name": name, "path": f"{base_url}{path}"} for name, path in PAGES.items()]
        urls_json = json.dumps(urls)

        # 4. 用 Playwright 截图
        print(f"📸 正在截取 {len(urls)} 张截图...")
        result = subprocess.run(
            ["node", WORKER_JS, urls_json, SCREENSHOT_DIR],
            capture_output=True, text=True, timeout=60, cwd=SCRIPT_DIR
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            stderr = result.stderr.strip()
            # Playwright 的 info 日志输出到 stderr，只有 FAIL 才报错
            if "FAIL" in stderr:
                print(f"⚠️ {stderr}")

        # 5. 验证截图
        for name in PAGES:
            fpath = os.path.join(SCREENSHOT_DIR, f"{name}.png")
            if os.path.exists(fpath):
                size_kb = os.path.getsize(fpath) / 1024
                print(f"  ✅ {name}.png ({size_kb:.1f} KB)")
            else:
                print(f"  ❌ {name}.png 缺失!")

        # 6. 如果指定了任务目录，复制过去
        if task_dir:
            for name in PAGES:
                src = os.path.join(SCREENSHOT_DIR, f"{name}.png")
                if os.path.exists(src):
                    dst_dir = os.path.join(task_dir, "screenshots")
                    os.makedirs(dst_dir, exist_ok=True)
                    shutil.copy2(src, os.path.join(dst_dir, f"{name}.png"))
            print(f"\n📋 截图已复制到: {task_dir}/screenshots/")

    finally:
        flask_proc.terminate()
        flask_proc.wait(timeout=5)

    return SCREENSHOT_DIR


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="截取异界军火商采购终端各页面截图")
    parser.add_argument("--port", type=int, default=5090, help="Flask 端口 (默认 5090)")
    parser.add_argument("--task-dir", help="同时复制截图到指定 GA 任务目录")
    args = parser.parse_args()
    capture(args.port, args.task_dir)
