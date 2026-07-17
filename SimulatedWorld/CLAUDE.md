# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**《暗夜堡垒：共生博弈》(Night Fortress: Symbiotic Game)** — a 1v1 competitive AI Agent evaluation platform disguised as a survival-strategy game. Two players each control 3 heroes (2 gatherer/builders + 1 pioneer) on a 25×25 grid, gathering resources, building defenses, completing tasks, and surviving 10 days (2000 turns) of escalating monster waves. The game evaluates agents across 5 dimensions: web interaction (A), causal reasoning (B), long-context memory (C), filesystem search (D), and code debugging (E).

**This repo** contains the web shop, test/evaluation framework, and design documents. The actual game engine and agent runtime live in the sibling project `/mnt/d/work/Hackthon/GenericAgent`.

## Repository Structure

```
web_shop/           # Flask web shop for Type-A (web interaction) tasks
  app.py            #   Main Flask app — 5 items, budget/constraint rules, 3 task modes (T1/T2/T5)
  capture_screenshots.py  # Starts Flask + uses Playwright to screenshot all pages
  screenshot_worker.js    # Playwright headless Chromium screenshot script
tests/              # Agent evaluation framework (LLM-as-judge)
  l1_standard_answers.py  # L1 standard answers: 3 text-based reasoning tasks with scoring rubrics
  eval_l1_results.py      # L1 scorer: runs GA agent, calls LLM judge, outputs dimension-level report
  l2_web_standard_answers.py  # L2 standard answers: 3 web-based tasks (T1/T2/T5) with scoring rubrics
  eval_l2_web.py           # L2 scorer: same LLM-as-judge pattern for web tasks
  run_l1_tests.sh          # Batch runner for L1 tests
  run_l2_web_tests.sh      # Full pipeline: Flask → screenshots → GA agent → optional eval
docs/               # Superpowers plans and specs
主要参考/           # Core design documents (Chinese)
  agent_task_system_design.md  # Complete task system design (A/B/C/D/E dimensions)
  agent_design.md              # Quest/scenario design (plague, stone tablet, scroll fragments)
  暗夜堡垒-共生博弈-设计文档.md  # Full game design doc (25×25 map, economy, combat, research tree)
其他/               # Competitive analysis of other AI agent competitions
```

## Key External Dependency

The game engine and agent runtime (`GenericAgent`) live at **`/mnt/d/work/Hackthon/GenericAgent`**. This is imported by `eval_l1_results.py` and `eval_l2_web.py` for LLM session management (`llmcore` module) and task execution (`agentmain.py`). Agent outputs are read from `{GA_DIR}/temp/{case_id}/output.txt`. The `mykey.py` configuration file in GenericAgent provides LLM API credentials.

## Commands

### Web Shop

```bash
# Start the Flask web shop (default port 5090)
cd web_shop && python3 app.py
# Custom port
python3 app.py --port 5091

# Capture screenshots of all shop pages (starts & stops Flask automatically)
python3 web_shop/capture_screenshots.py
# Screenshot + copy to GA task directory
python3 web_shop/capture_screenshots.py --task-dir /mnt/d/work/Hackthon/GenericAgent/temp/l2_web_t1

# Install Playwright dependency (one-time)
cd web_shop && npm install && npx playwright install chromium
```

### Running Agent Tests

```bash
# L1 tests (text-based reasoning tasks: stone, plague, scroll)
cd tests
./run_l1_tests.sh              # Run all 3
./run_l1_tests.sh stone        # Single test
./run_l1_tests.sh --eval       # Run + LLM evaluation

# L2 tests (web interaction tasks: T1/T2/T5)
./run_l2_web_tests.sh          # Flask → screenshots → GA agent (all 3 tasks)
./run_l2_web_tests.sh t1       # Single task
./run_l2_web_tests.sh --eval   # Full pipeline + LLM evaluation

# Python scorer directly (for custom cases or re-evaluation)
python3 tests/eval_l1_results.py --case l1_test_stone
python3 tests/eval_l1_results.py --run-first       # Run tests then evaluate
python3 tests/eval_l2_web.py --case l2_web_t1
```

### Scoring Reports

Evaluation reports are saved as JSON:
- `tests/l1_eval_report.json` — dimension-level scores for L1 tasks
- `tests/l2_web_eval_report.json` — dimension-level scores for L2 web tasks

## Architecture Notes

### Web Shop Design (Type-A Tasks)

The web shop implements an "AI arms dealer terminal" theme with three task modes of increasing difficulty:

- **T1 (★☆)**: Shopping list — agent reads a fixed purchase instruction ("buy items #1 and #2")
- **T2 (★★☆)**: Constraint optimization — agent must figure out which items maximize "attack power" while respecting mutual exclusion (#1 ↔ #3)
- **T5 (★★★★)**: Information jigsaw — main page hides prices/effects; agent must explore all 5 sub-pages (weapons, defense, utility, rules, intel) and integrate cross-page information

Two CSS themes: default "retro sci-fi terminal" dark theme, and `?theme=ocr` for high-contrast OCR-friendly rendering used by screenshots.

The shop enforces: 100 gold budget, mutual exclusion between items #1 and #3, max 2 items, and purchase validation via `/api/purchase` POST endpoint.

### Test Framework Pattern

Both L1 and L2 evaluators follow the same pattern:
1. Run GA agent via subprocess (`agentmain.py --task {case_id}`)
2. Load standard answers from the corresponding `*_standard_answers.py`
3. Build an LLM evaluation prompt with dimensions, criteria, and weights
4. Call LLM via the GenericAgent `NativeOAISession` or fallback `MixinSession`
5. Parse JSON score from LLM response
6. Print a bar-chart report and save JSON results

Standard answers define scoring dimensions (e.g., intent recognition, constraint checking, decision quality) with weights summing to 100 per case.

### Task System Design (from reference docs)

The game uses a **task officer** system for active tasks (A/D/E) and **world news** for passive tasks (B/C):

- **Task officer**: Pioneer visits the task hall (fixed map coordinate), judge randomly assigns one of A/D/E tasks. Complete or fail → next random task. Max 5 failures per task before auto-abandon.
- **World news [Official]**: Daily intelligence that affects game parameters and merchant prices. Agent reasons about causality and preempts resource shortages.
- **World news [Folklore]**: 4 fragments scattered across 7 days — agent must collect all, map NL descriptions to game items, then execute at the correct location in correct order.

The anti-hardcoding design is deliberate: every match has different file contents, directory structures, bug locations, and clue types to force agents to genuinely reason rather than follow fixed procedures.
