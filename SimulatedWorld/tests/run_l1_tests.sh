#!/bin/bash
# ============================================================
# L1 Agent 任务理解能力 — 批量测试执行脚本
# ============================================================
# 用法:
#   ./run_l1_tests.sh              # 运行全部3个测试
#   ./run_l1_tests.sh stone        # 只跑石碑任务
#   ./run_l1_tests.sh --eval       # 运行+评分
# ============================================================

set -e

GA_DIR="/mnt/d/work/Hackthon/GenericAgent"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ALL_CASES=("l1_test_stone" "l1_test_plague" "l1_test_scroll")
CASES=("${ALL_CASES[@]}")

DO_EVAL=false

# 解析参数
for arg in "$@"; do
    case "$arg" in
        --eval) DO_EVAL=true ;;
        stone)  CASES=("l1_test_stone") ;;
        plague) CASES=("l1_test_plague") ;;
        scroll) CASES=("l1_test_scroll") ;;
    esac
done

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  L1 Agent 任务理解能力 — 批量测试${NC}"
echo -e "${CYAN}  用例数: ${#CASES[@]}${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

PASSED=0
FAILED=0
TIMINGS=()

for case_id in "${CASES[@]}"; do
    TASK_DIR="$GA_DIR/temp/$case_id"
    INPUT_FILE="$TASK_DIR/input.txt"

    if [ ! -f "$INPUT_FILE" ]; then
        echo -e "  ${RED}❌ $case_id: input.txt 不存在${NC}"
        FAILED=$((FAILED + 1))
        continue
    fi

    # 清理旧输出
    rm -f "$TASK_DIR"/output*.txt "$TASK_DIR"/stdout.log "$TASK_DIR"/stderr.log

    echo -n "  🏃 $case_id ... "

    START_TIME=$(date +%s)

    # 运行 Agent
    cd "$GA_DIR"
    timeout 300 python3 agentmain.py --task "$case_id" --nobg \
        > "$TASK_DIR/stdout.log" 2> "$TASK_DIR/stderr.log"
    EXIT_CODE=$?

    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))

    OUTPUT_FILE="$TASK_DIR/output.txt"

    if [ -f "$OUTPUT_FILE" ] && grep -q "ROUND END" "$OUTPUT_FILE" 2>/dev/null; then
        SIZE=$(wc -c < "$OUTPUT_FILE")
        echo -e "${GREEN}✅ ${ELAPSED}s, ${SIZE} bytes${NC}"
        PASSED=$((PASSED + 1))
        TIMINGS+=("$case_id: ${ELAPSED}s")
    elif [ -f "$OUTPUT_FILE" ]; then
        SIZE=$(wc -c < "$OUTPUT_FILE")
        echo -e "${YELLOW}⚠️  ${ELAPSED}s, ${SIZE} bytes (未完成? 无 [ROUND END])${NC}"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}❌ ${ELAPSED}s, exit=${EXIT_CODE}, 无输出${NC}"
        # 打印错误日志的最后几行
        if [ -f "$TASK_DIR/stderr.log" ] && [ -s "$TASK_DIR/stderr.log" ]; then
            echo "      stderr: $(tail -3 "$TASK_DIR/stderr.log" | tr '\n' ' ')"
        fi
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo -e "${CYAN}------------------------------------------------------------${NC}"
echo -e "${CYAN}  结果: ${GREEN}$PASSED 通过${NC} / ${RED}$FAILED 失败${NC} / $((PASSED + FAILED)) 总计${NC}"
for t in "${TIMINGS[@]}"; do
    echo -e "    ⏱️  $t"
done
echo -e "${CYAN}------------------------------------------------------------${NC}"

# 如果指定了 --eval，自动运行评分
if $DO_EVAL && [ $PASSED -gt 0 ]; then
    echo ""
    echo -e "${CYAN}📊 运行 LLM 评分 ...${NC}"
    cd "$SCRIPT_DIR"
    python3 eval_l1_results.py --no-run
fi
