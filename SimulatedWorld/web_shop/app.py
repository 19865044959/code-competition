#!/usr/bin/env python3
"""
异界军火商 · 采购终端 — Flask Web Shop
为 Agent 网页操作（Type B）任务提供本地 WebUI

用法:
  python3 app.py                  # 默认端口 5090
  python3 app.py --port 5091      # 自定义端口
"""

import sys, os, json, argparse
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# ─── 商品数据 ───
ITEMS = {
    1: {"name": "瞄准镜组件", "effect": "防御塔攻击力 +20%", "price": 45, "category": "攻击", "spec_page": "weapons"},
    2: {"name": "纳米涂层",   "effect": "围墙防御力 +30%",   "price": 40, "category": "防御", "spec_page": "defense"},
    3: {"name": "脉冲发生器", "effect": "防御塔射程 +1格",   "price": 55, "category": "射程", "spec_page": "weapons"},
    4: {"name": "能量核心",   "effect": "基地获得额外 800 HP","price": 80, "category": "防御", "spec_page": "defense"},
    5: {"name": "夜视目镜",   "effect": "英雄夜间视野 +2格",  "price": 10, "category": "辅助", "spec_page": "utility"},
}

BUDGET = 100
MAX_ITEMS = 2
MUTUAL_EXCLUSION = {1, 3}  # 瞄准镜 ↔ 脉冲发生器 互斥

# ─── 指令行内容（按任务类型） ───
INSTRUCTIONS = {
    "t1": '📋 本次采购指令：\n"前线指挥官要求购买【瞄准镜组件】和【纳米涂层】"',
    "t2": '📋 本次采购指令：\n"选择2件商品，最大化防御塔的攻击能力。\n 注意：你的选择不能触发互斥规则。"',
    "t5": '📋 本次采购指令：\n"请浏览所有子页面获取完整信息后做出购买决策。"',
}

INTEL_CONTENT = {
    "t1": "前线战报：指挥官明确要求采购瞄准镜组件和纳米涂层，以提升防御塔火力和围墙耐久度。",
    "t2": "军情分析：当前防御塔攻击力不足，前线急需提升火力输出。请优先考虑直接增强攻击能力的装备。",
    "t5": '战略简报：选择2件商品，最大化防御塔的攻击能力。注意：你的选择不能触发互斥规则。',
}

# ─── CSS 样式 ───
# ?theme=ocr 时使用高对比度 OCR 友好主题，默认使用复古科幻终端风

def get_style(ocr_mode=False):
    if ocr_mode:
        return """
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #ffffff; color: #111111; font-family: Arial, sans-serif;
    padding: 20px; min-height: 100vh; font-size: 15px;
  }
  .terminal {
    max-width: 780px; margin: 0 auto;
    border: 2px solid #333; border-radius: 4px;
    background: #ffffff; padding: 24px;
  }
  .header { text-align: center; border-bottom: 1px solid #333; padding-bottom: 16px; margin-bottom: 20px; }
  .header h1 { color: #111; font-size: 22px; }
  .header .sub { color: #555; font-size: 12px; margin-top: 4px; }
  .balance { text-align: right; font-size: 16px; margin-bottom: 12px; color: #333; font-weight: bold; }
  .instruction { background: #f5f5f5; border-left: 3px solid #333; padding: 12px 16px; margin-bottom: 20px; font-size: 14px; line-height: 1.8; white-space: pre-line; color: #111; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
  th { text-align: left; padding: 10px 8px; border-bottom: 2px solid #333; color: #111; font-size: 13px; font-weight: bold; }
  td { padding: 10px 8px; border-bottom: 1px solid #ddd; font-size: 14px; color: #111; }
  .checkbox { width: 20px; height: 20px; border: 2px solid #333; display: inline-block; text-align: center; line-height: 16px; font-size: 16px; color: #333; background: #fff; }
  .checkbox.checked { background: #333; color: #fff; }
  .price { color: #333; font-weight: bold; }
  .detail-link { color: #0066cc; }
  .rules-box { background: #f9f9f9; border: 1px solid #ddd; padding: 14px 18px; margin-bottom: 20px; font-size: 13px; line-height: 2; color: #111; }
  .rules-box .title { color: #cc3300; font-weight: bold; margin-bottom: 6px; }
  .btn { display: block; width: 100%; padding: 12px; text-align: center; background: #333; color: #fff; border: none; border-radius: 4px; font-size: 16px; font-weight: bold; }
  .footer-links { margin-top: 18px; padding-top: 14px; border-top: 1px solid #ddd; display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; }
  .footer-links a { color: #0066cc; }
  .spec-page h2 { color: #111; margin-bottom: 16px; font-size: 18px; }
  .spec-card { background: #f9f9f9; border: 1px solid #ddd; padding: 16px; margin-bottom: 14px; }
  .spec-card h3 { color: #333; font-size: 16px; margin-bottom: 8px; }
  .spec-card .attr { font-size: 14px; line-height: 2; color: #111; }
  .spec-card .mutex { color: #cc0000; font-weight: bold; }
  .back-link { display: inline-block; margin-top: 16px; color: #0066cc; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 11px; margin-left: 6px; border: 1px solid #999; }
  .tag-attack { background: #ffeeee; color: #cc0000; }
  .tag-def { background: #eeeeff; color: #0000cc; }
  .tag-util { background: #eeffee; color: #006600; }
</style>"""

    # 默认：复古科幻终端风
    return """
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #0a0e14; color: #b3e5d9; font-family: 'Courier New', monospace;
    padding: 20px; min-height: 100vh;
  }
  .terminal {
    max-width: 780px; margin: 0 auto;
    border: 2px solid #1a3a4a; border-radius: 8px;
    background: #0d151c; padding: 24px;
    box-shadow: 0 0 30px rgba(0, 180, 160, 0.08);
  }
  .header {
    text-align: center; border-bottom: 1px solid #1a3a4a;
    padding-bottom: 16px; margin-bottom: 20px;
  }
  .header h1 { color: #00d4aa; font-size: 22px; letter-spacing: 2px; }
  .header .sub { color: #5a7a8a; font-size: 12px; margin-top: 4px; }
  .balance {
    text-align: right; font-size: 16px; margin-bottom: 12px;
    color: #ffd700;
  }
  .instruction {
    background: #111a22; border-left: 3px solid #00d4aa;
    padding: 12px 16px; margin-bottom: 20px;
    font-size: 14px; line-height: 1.8; white-space: pre-line;
    color: #c0e8d5;
  }
  table { width: 100%; border-collapse: collapse; margin-bottom: 16px; }
  th {
    text-align: left; padding: 10px 8px; border-bottom: 2px solid #1a3a4a;
    color: #7ab8a0; font-size: 13px; text-transform: uppercase; letter-spacing: 1px;
  }
  td { padding: 10px 8px; border-bottom: 1px solid #111a22; font-size: 14px; }
  tr:hover { background: #111a22; }
  .checkbox {
    width: 20px; height: 20px; border: 2px solid #00d4aa; display: inline-block;
    text-align: center; line-height: 16px; font-size: 16px; color: #00d4aa;
    cursor: pointer; background: #0a0e14;
  }
  .checkbox.checked { background: #00d4aa; color: #0a0e14; }
  .price { color: #ffd700; font-weight: bold; }
  .detail-link { color: #00aacc; text-decoration: none; font-size: 12px; }
  .detail-link:hover { text-decoration: underline; }
  .rules-box {
    background: #0f1818; border: 1px solid #1a3a4a; border-radius: 4px;
    padding: 14px 18px; margin-bottom: 20px; font-size: 13px; line-height: 2;
  }
  .rules-box .title { color: #ff8c42; font-weight: bold; margin-bottom: 6px; }
  .btn {
    display: block; width: 100%; padding: 12px; text-align: center;
    background: #00d4aa; color: #0a0e14; border: none; border-radius: 4px;
    font-size: 16px; font-weight: bold; cursor: pointer; letter-spacing: 3px;
    font-family: 'Courier New', monospace;
  }
  .btn:hover { background: #00ffcc; }
  .footer-links {
    margin-top: 18px; padding-top: 14px; border-top: 1px solid #1a3a4a;
    display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px;
  }
  .footer-links a { color: #5a9aaa; text-decoration: none; }
  .footer-links a:hover { color: #00d4aa; text-decoration: underline; }
  .spec-page h2 { color: #00d4aa; margin-bottom: 16px; font-size: 18px; }
  .spec-card {
    background: #111a22; border: 1px solid #1a3a4a; border-radius: 4px;
    padding: 16px; margin-bottom: 14px;
  }
  .spec-card h3 { color: #ffd700; font-size: 16px; margin-bottom: 8px; }
  .spec-card .attr { font-size: 14px; line-height: 2; color: #b3e5d9; }
  .spec-card .mutex { color: #ff6b6b; font-weight: bold; }
  .back-link { display: inline-block; margin-top: 16px; color: #5a9aaa; text-decoration: none; }
  .back-link:hover { color: #00d4aa; }
  .tag {
    display: inline-block; padding: 2px 8px; border-radius: 3px;
    font-size: 11px; margin-left: 6px;
  }
  .tag-attack { background: #4a1a1a; color: #ff6b6b; }
  .tag-def { background: #1a2a4a; color: #6ba3ff; }
  .tag-util { background: #1a3a1a; color: #6bff6b; }
</style>
"""

# ─── 基础布局 ───
def base_page(content: str, title: str = "采购终端", ocr_mode: bool = False) -> str:
    style = get_style(ocr_mode)
    return f"""<!DOCTYPE html>
<html lang="zh">
<head><meta charset="UTF-8"><title>{title}</title>{style}</head>
<body><div class="terminal">{content}</div></body>
</html>"""

# ─── 主页 ───
@app.route("/shop/<sid>")
def shop(sid):
    ocr = request.args.get("theme") == "ocr"
    instr = INSTRUCTIONS.get(sid, INSTRUCTIONS["t1"])
    show_details = (sid != "t5")  # T5: 隐藏详情

    rows = ""
    for i in sorted(ITEMS.keys()):
        item = ITEMS[i]
        price_display = f'<span class="price">{item["price"]}</span>' if show_details else '<span style="color:#5a7a8a;">详见</span>'
        effect_display = item["effect"] if show_details else f'<a class="detail-link" href="/specs/{item["spec_page"]}">详见规格页</a>'
        tag_html = ""
        if item["category"] == "攻击":
            tag_html = '<span class="tag tag-attack">攻击</span>'
        elif item["category"] == "防御":
            tag_html = '<span class="tag tag-def">防御</span>'
        else:
            tag_html = '<span class="tag tag-util">辅助</span>'

        rows += f"""
        <tr>
          <td>#{i}</td>
          <td>{item['name']}{tag_html}</td>
          <td>{effect_display}</td>
          <td>{price_display}</td>
          <td><span class="checkbox" id="cb{i}" onclick="this.classList.toggle('checked')"></span></td>
        </tr>"""

    rules_html = """
    <div class="rules-box">
      <div class="title">⚠️ 购买规则</div>
      ① 每人预算 <b>100 金币</b>，超预算无法提交订单<br>
      ② <b>#1 瞄准镜组件</b> 与 <b>#3 脉冲发生器</b> 互斥（占用同一接口槽位），不能同时勾选<br>
      ③ 每人限购 <b>2 件</b>不同商品<br>
      ④ 所有效果购买后<b>永久生效</b>
    </div>"""

    footer = """
    <div class="footer-links">
      📎 <a href="/specs/weapons">武器规格</a>
      | <a href="/specs/defense">防御规格</a>
      | <a href="/specs/utility">辅助规格</a>
      | <a href="/rules">购买规则</a>
      | <a href="/intel?task={sid}">战场情报</a>
    </div>""".replace("{sid}", sid)

    content = f"""
    <div class="header">
      <h1>🌌 异界军火商 · 采购终端</h1>
      <div class="sub">SESSION: {sid.upper()} | 终端已就绪</div>
    </div>
    <div class="balance">💰 余额：<b>{BUDGET}</b> 金币</div>
    <div class="instruction">{instr}</div>
    <table>
      <tr><th>#</th><th>商品</th><th>效果</th><th>价格</th><th>勾选</th></tr>
      {rows}
    </table>
    {rules_html}
    <button class="btn" onclick="submitOrder()">[ 购 买 ]</button>
    {footer}
    <script>
    function submitOrder() {{
      var items = [];
      for (var i = 1; i <= 5; i++) {{
        var cb = document.getElementById('cb' + i);
        if (cb && cb.classList.contains('checked')) items.push(i);
      }}
      fetch('/api/purchase', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{items: items}})
      }})
      .then(r => r.json())
      .then(data => {{
        if (data.success) {{
          alert('✅ 购买成功！\\n\\n已购买: ' + data.purchased.join('、') + '\\n总价: ' + data.total + ' 金币\\n剩余: ' + data.remaining + ' 金币');
        }} else {{
          alert('❌ 购买失败\\n\\n' + data.error);
        }}
      }});
    }}
    </script>"""
    return base_page(content, f"采购终端 - {sid.upper()}", ocr_mode=ocr)

# ─── 规格子页面 ───
@app.route("/specs/<category>")
def specs(category):
    ocr = request.args.get("theme") == "ocr"
    pages = {
        "weapons": {
            "title": "⚔️ 武器配件规格",
            "items": [1, 3],
        },
        "defense": {
            "title": "🛡️ 防御装备规格",
            "items": [2, 4],
        },
        "utility": {
            "title": "🔧 辅助装备规格",
            "items": [5],
        },
    }
    page = pages.get(category, pages["weapons"])
    cards = ""
    for i in page["items"]:
        item = ITEMS[i]
        mutex_html = ""
        if i in MUTUAL_EXCLUSION:
            other = [x for x in MUTUAL_EXCLUSION if x != i][0]
            mutex_html = f'<br><span class="mutex">⚠️ 互斥：本商品与 #{other} {ITEMS[other]["name"]} 冲突（占用同一接口槽位）</span>'
        cards += f"""
    <div class="spec-card">
      <h3>#{i} {item['name']}</h3>
      <div class="attr">
        效果：{item['effect']}<br>
        价格：<span class="price">{item['price']} 金币</span><br>
        类别：{item['category']}{mutex_html}
      </div>
    </div>"""

    content = f"""
    <div class="spec-page">
      <h2>{page['title']}</h2>
      {cards}
      <a class="back-link" href="javascript:history.back()">← 返回主页</a>
    </div>"""
    return base_page(content, page["title"], ocr_mode=ocr)

# ─── 规则页 ───
@app.route("/rules")
def rules():
    ocr = request.args.get("theme") == "ocr"
    content = """
    <div class="spec-page">
      <h2>📜 采购规则</h2>
      <div class="rules-box" style="line-height:2.4;font-size:14px;">
        ① 每人预算 <b>100 金币</b>，超预算无法提交订单<br>
        ② <b>#1 瞄准镜</b> 与 <b>#3 脉冲发生器</b> 互斥（占用同一接口槽位）<br>
        ③ 每人限购 <b>2 件</b>不同商品<br>
        ④ 所有效果购买后<b>永久生效</b>
      </div>
      <a class="back-link" href="javascript:history.back()">← 返回主页</a>
    </div>"""
    return base_page(content, "采购规则", ocr_mode=ocr)

# ─── 情报页 ───
@app.route("/intel")
def intel():
    ocr = request.args.get("theme") == "ocr"
    task = request.args.get("task", "t1")
    intel_text = INTEL_CONTENT.get(task, INTEL_CONTENT["t1"])
    content = f"""
    <div class="spec-page">
      <h2>📋 战场情报</h2>
      <div class="instruction" style="line-height:2.4;font-size:14px;">
        {intel_text}
      </div>
      <a class="back-link" href="javascript:history.back()">← 返回主页</a>
    </div>"""
    return base_page(content, "战场情报", ocr_mode=ocr)

# ─── 购买 API ───
@app.route("/api/purchase", methods=["POST"])
def purchase():
    data = request.get_json(force=True)
    items = data.get("items", [])

    # 去重
    items = sorted(set(int(i) for i in items))

    # 校验：商品存在
    for i in items:
        if i not in ITEMS:
            return jsonify({"success": False, "error": f"商品 #{i} 不存在。"})

    # 校验：限购 2 件
    if len(items) > MAX_ITEMS:
        return jsonify({"success": False, "error": f"限购 {MAX_ITEMS} 件，你选择了 {len(items)} 件。请取消多余选择。"})

    if len(items) == 0:
        return jsonify({"success": False, "error": "请至少选择 1 件商品。"})

    # 校验：互斥
    selected_set = set(items)
    if MUTUAL_EXCLUSION.issubset(selected_set):
        return jsonify({"success": False, "error": f"#1 瞄准镜组件 与 #3 脉冲发生器 互斥（占用同一接口槽位），请重新选择。"})

    # 校验：预算
    total = sum(ITEMS[i]["price"] for i in items)
    if total > BUDGET:
        return jsonify({"success": False, "error": f"总价 {total} 金币，超过预算 {BUDGET} 金币，请重新选择。"})

    # 成功
    names = [ITEMS[i]["name"] for i in items]
    return jsonify({
        "success": True,
        "purchased": names,
        "total": total,
        "remaining": BUDGET - total,
        "message": f"购买成功！{', '.join(names)} 将在游戏中永久生效。"
    })

# ─── 首页 ───
@app.route("/")
def index():
    content = """
    <div class="header">
      <h1>🌌 异界军火商 · 采购终端</h1>
      <div class="sub">请选择任务入口</div>
    </div>
    <div style="text-align:center;padding:40px;">
      <p style="margin-bottom:24px;color:#5a7a8a;">选择你要进入的采购场景：</p>
      <a href="/shop/t1" style="display:block;margin:8px;padding:12px;background:#111a22;color:#00d4aa;text-decoration:none;border-radius:4px;">📦 T1 — 购物清单型（基础阅读+执行）</a>
      <a href="/shop/t2" style="display:block;margin:8px;padding:12px;background:#111a22;color:#00d4aa;text-decoration:none;border-radius:4px;">🎯 T2 — 约束寻优型（多约束下自主决策）</a>
      <a href="/shop/t5" style="display:block;margin:8px;padding:12px;background:#111a22;color:#00d4aa;text-decoration:none;border-radius:4px;">🧩 T5 — 信息拼图型（跨页面信息整合）</a>
    </div>"""
    return base_page(content, "采购终端")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5090)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    print(f"🚀 异界军火商采购终端启动: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
