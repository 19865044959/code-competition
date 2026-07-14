#!/bin/bash
# L2 Web Agent 测试 — 一键运行脚本
# 用法:
#   ./run_l2_web_tests.sh              # 运行全部 3 个测试
#   ./run_l2_web_tests.sh t1           # 只运行 T1
#   ./run_l2_web_tests.sh --eval       # 运行全部 + 评估
#
# 流程:
#   1. 启动 Flask WebUI (后台)
#   2. Playwright 截图 → 复制到 GA 任务目录
#   3. 运行 GA agentmain.py --task l2_web_t1/t2/t5
#   4. 可选: 运行 eval_l2_web.py 评估

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GA_DIR="/mnt/d/work/Hackthon/GenericAgent"
WEB_SHOP_DIR="$SCRIPT_DIR/../web_shop"
PORT=5090
TIMEOUT=600  # 10 分钟超时（网页任务需要解析多张截图）

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 解析参数
DO_EVAL=false
TEST_FILTER=""

for arg in "$@"; do
    case $arg in
        --eval) DO_EVAL=true ;;
        t1|t2|t5) TEST_FILTER="$arg" ;;
    esac
done

# 确定要运行的测试
if [ -n "$TEST_FILTER" ]; then
    CASES=("l2_web_$TEST_FILTER")
else
    CASES=("l2_web_t1" "l2_web_t2" "l2_web_t5")
fi

echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  L2 Web Agent 网页操作能力测试${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo "  测试用例: ${CASES[*]}"
echo "  评测模式: $([ "$DO_EVAL" = true ] && echo '是' || echo '否')"
echo ""

# ─── Step 1: 启动 Flask ───
echo -e "${YELLOW}[1/3] 启动 Flask WebUI ...${NC}"
cd "$WEB_SHOP_DIR"
python3 app.py --port $PORT &
FLASK_PID=$!
sleep 2

# 验证 Flask 是否启动
if ! kill -0 $FLASK_PID 2>/dev/null; then
    echo -e "${RED}❌ Flask 启动失败${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Flask 已启动 (PID: $FLASK_PID, Port: $PORT)${NC}"

# ─── Step 2: 截图（每次重新截取） ───
echo -e "\n${YELLOW}[2/3] Playwright 截图 ...${NC}"

for case_id in "${CASES[@]}"; do
    TASK_DIR="$GA_DIR/temp/$case_id"
    echo "  📸 截图 → $case_id"
    python3 "$WEB_SHOP_DIR/capture_screenshots.py" --port $PORT --task-dir "$TASK_DIR" > /dev/null 2>&1
    echo -e "  ${GREEN}✅ $case_id 截图完成${NC}"
done

# 停掉 Flask（截图完成，不需要了）
kill $FLASK_PID 2>/dev/null
wait $FLASK_PID 2>/dev/null
echo -e "${GREEN}✅ Flask 已关闭${NC}"

# ─── Step 3: 运行 GA 测试 ───
echo -e "\n${YELLOW}[3/3] 运行 GA Agent 测试 ...${NC}"

PASS=0
FAIL=0

for case_id in "${CASES[@]}"; do
    TASK_DIR="$GA_DIR/temp/$case_id"
    echo ""
    echo "  ── $case_id ──"

    # 清理旧输出
    rm -f "$TASK_DIR/output.txt" "$TASK_DIR/output0.txt" "$TASK_DIR/stdout.log" "$TASK_DIR/stderr.log"

    echo -n "  🏃 运行中 ... "

    START_TIME=$(date +%s)

    cd "$GA_DIR"
    timeout $TIMEOUT python3 agentmain.py --task "$case_id" --nobg \
        > "$TASK_DIR/stdout.log" 2> "$TASK_DIR/stderr.log"
    EXIT_CODE=$?

    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))

    # 检查结果
    OUTPUT_FILE="$TASK_DIR/output.txt"
    if [ ! -f "$OUTPUT_FILE" ] && [ -f "$TASK_DIR/output0.txt" ]; then
        cp "$TASK_DIR/output0.txt" "$OUTPUT_FILE"
    fi

    if [ -f "$OUTPUT_FILE" ]; then
        SIZE=$(wc -c < "$OUTPUT_FILE")
        HAS_END=$(grep -c "ROUND END" "$OUTPUT_FILE" 2>/dev/null || true)

        if [ "$HAS_END" -gt 0 ] || [ "$SIZE" -gt 100 ]; then
            echo -e "${GREEN}✅ 成功${NC} (${ELAPSED}s, ${SIZE} bytes)"
            PASS=$((PASS + 1))
        else
            echo -e "${RED}❌ 输出不完整${NC} (${ELAPSED}s, ${SIZE} bytes)"
            FAIL=$((FAIL + 1))
        fi
    else
        echo -e "${RED}❌ 无输出文件${NC} (exit=$EXIT_CODE, ${ELAPSED}s)"
        FAIL=$((FAIL + 1))
        if [ -f "$TASK_DIR/stderr.log" ] && [ -s "$TASK_DIR/stderr.log" ]; then
            echo "      stderr: $(tail -3 "$TASK_DIR/stderr.log")"
        fi
    fi
done

# ─── 汇总 ───
echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "  结果: ${GREEN}$PASS 通过${NC} / ${RED}$FAIL 失败${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"

# ─── 评估（可选） ───
if [ "$DO_EVAL" = true ]; then
    echo ""
    echo -e "${YELLOW}📊 运行 LLM 评测 ...${NC}"
    cd "$SCRIPT_DIR"
    python3 eval_l2_web.py
fi
