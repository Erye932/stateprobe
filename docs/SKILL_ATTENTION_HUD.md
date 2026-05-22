# StateProbe Skill：Agent 注意力外部控制层

StateProbe Skill 是给 agent 用的外部控制层。

它的核心作用很简单：**agent 正式输出之前，先检查它有没有听懂、准备往哪儿写、要不要先停一下。**

它有两个模式：

- `preview`：写之前用。对比“用户真正要什么”和“agent 准备关注什么”。
- `overlay`：写之后用。对比“用户真正要什么”和“agent 实际写了什么”。

两个模式都在做同一件事：

- 把用户要求拆出来
- 把 agent 的计划或输出拆出来
- 找出两边哪里对齐、哪里跑偏
- 给出下一步控制动作

`preview` 会直接告诉 host：继续、重写、追问用户，还是切断旧上下文。

这一层是**任务层注意力**，不读模型 hidden states、logits、attention heads、router traces，也不读任何模型内部。真正的内部向量和激活扫描属于 Enterprise Runtime Probe 方向。

## 什么时候用

当你想在 agent 输出前后确认这些事，就用它：

- 写之前，agent 准备把重点放在哪里？
- 用户最重要的要求有没有被漏掉？
- 现在能不能继续写，还是应该先停下来重写计划？
- 画图 / 视频生成前，哪些东西必须出现，哪些只能暗示，哪些不能出现？
- “打游戏”“情绪崩溃”“科技感”这类词会不会被模型画成多余 UI、文字、符号特效？
- 边界不清楚时，应该先问用户哪一句？
- 写完之后，agent 有没有真的围绕用户重点输出？
- 哪些要求被满足、被弱化、被忽略、被违反？
- 如果继续沿着现在方向写，会越来越偏向什么？
- 下一轮应该加强什么、压低什么、停止什么、回到什么？

## CLI usage

写之前先跑 `preview`：

```bash
stateprobe skill preview \
  --context-text "核心是让 agent 的注意力可见。不要把格式化当主线。" \
  --plan-text "我准备重点写 prompt 检查器和格式化模板。" \
  --json
```

`preview` 会返回 `risk_level`、`should_continue`、`planned_attention_map`、`missing_before_start`、`opening_patch`、`control_levers`、`boundary_decomposition`、`literalization_risks`、`boundary_questions`、`context_contamination_risks` 和 `activation_decision`。

其中最重要的是 `activation_decision`。host 不需要自己猜该怎么办，直接按它的 `action` 分支：

- `continue`：理解基本对齐，可以继续。
- `rewrite_planned_focus`：计划已经偏了，先按 `opening_patch` 重写，再输出。
- `ask_boundary_question`：边界不清楚，先把问题抛给用户确认。
- `cut_context_contamination`：被旧上下文带偏了，先砍掉旧方向，再回到用户最新要求。

它还带 `should_stop`、`reason`、`message`、`blockers`、`next_steps`，方便 host 直接执行，不用重新从其他字段里推断控制流。

对画图 / 视频生成任务，下面这些边界字段最重要：

- `boundary_decomposition.must_show`：必须直接出现的东西
- `boundary_decomposition.can_imply`：可以用姿态、构图、表情、氛围来暗示的动作或状态
- `boundary_decomposition.must_not_show`：明确不能出现的东西
- `literalization_risks`：哪些词可能被模型画成多余的可见内容
- `boundary_questions`：生成前应该问用户的 A/B/C 确认题
- `context_contamination_risks`：哪些旧上下文可能正在把 `planned_focus` 带偏

例子：

```bash
stateprobe skill preview \
  --context-text "小男孩拿着手机打游戏，重点是小男孩的沉浸感。" \
  --plan-text "我准备画一个小男孩拿着手机，手机屏幕上显示游戏画面。"
```

这个例子里，`preview` 会给出类似这样的边界判断：

- `must_show`: `小男孩`, `手机`
- `can_imply`: `打游戏`, `沉浸感`
- risk: `"打游戏"` 可能被模型画成手机屏幕上的游戏 UI
- question: `你是否真的想看到打游戏的画面？`

默认终端输出是给人看的产品视图：展示边界判断、字面化风险、需要追问的问题、旧上下文污染和下一步修正建议。它不会默认展示底层注意力表，避免第一屏太吵。

需要看底层证据时，再加 `--debug`：

```bash
stateprobe skill preview \
  --context-text "小男孩拿着手机打游戏，重点是小男孩的沉浸感。" \
  --plan-text "我准备画一个小男孩拿着手机，手机屏幕上显示游戏画面。" \
  --debug
```

`--json` 永远返回完整机器可读结果，包括底层表。

### Agent 激活流程

Agent host 应该默认走“写之前先 preview”的流程：

1. 把用户当前要求、重点、不要做什么收成 `context`。
2. 让 agent 先写一句短的 `planned_focus`，说明自己准备围绕什么输出。
3. 正式写或生成之前，调用 `stateprobe skill preview` 或 MCP 的 `stateprobe_preview_attention`。
4. 按 `activation_decision.action` 分支：
   - `continue`：开始输出。
   - `rewrite_planned_focus`：应用 `next_steps`，重写计划，再跑一次 preview。
   - `ask_boundary_question`：把 `activation_decision.message` 问给用户，把回答合并回 `context`，必要时再跑 preview。
   - `cut_context_contamination`：从当前计划里删掉旧上下文残留，重新对准用户最新要求。
5. 只要 `activation_decision.should_stop` 是 `true`，host 就不应该让 agent 继续输出用户可见内容。

Minimal host instruction:

```text
在正式回答、画图、生成视频之前，先用当前用户要求和你的 planned_focus 跑 StateProbe preview。
读取 activation_decision.action，并按 next_steps 执行。
activation_decision.should_stop 为 true 时，不要输出用户可见内容。
```

写完之后跑 `overlay` 时，准备两个文件：

- 一个 `context` 文件：放用户要求
- 一个 `output` 文件：放 agent 实际输出

仓库里已经有示例文件：

```bash
stateprobe skill overlay \
  --context examples/skill_attention_context.txt \
  --output examples/skill_attention_output.txt
```

机器可读 JSON：

```bash
stateprobe skill overlay \
  --context examples/skill_attention_context.txt \
  --output examples/skill_attention_output.txt \
  --json
```

只打印下一轮纠偏建议：

```bash
stateprobe skill overlay \
  --context examples/skill_attention_context.txt \
  --output examples/skill_attention_output.txt \
  --control-patch
```

### 不落盘调用

Agent host 可以不写文件，直接把文本传进来。三种输入方式**互斥**：

| 输入方式 | 参数 | 什么时候用 |
|---|---|---|
| 文件路径 | `--context PATH --output PATH` | 手动探索、脚本 |
| 直接文本 | `--context-text TEXT --output-text TEXT` | 短输入、命令行拼接 |
| stdin JSON | `--stdin-json` 读取 `{"context": "...", "output": "..."}` | agent host、MCP server、跨语言集成 |

直接传文本：

```bash
stateprobe skill overlay \
  --context-text "核心是让 agent 的注意力可见。不要把格式化当主线。" \
  --output-text  "StateProbe 是一个 prompt 检查器，格式化模板是核心。" \
  --json
```

stdin JSON（推荐给 agent 集成用，少踩 shell 转义和编码坑）：

```bash
echo '{"context":"核心是让 agent 的注意力可见。","output":"我们做一个完全无关的天气预报应用。"}' \
  | stateprobe skill overlay --stdin-json --json
```

Python subprocess 示例：

```python
import json, subprocess
payload = {"context": user_requirements, "output": agent_response}
proc = subprocess.run(
    ["stateprobe", "skill", "overlay", "--stdin-json", "--json"],
    input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    capture_output=True,
    check=True,
)
hud = json.loads(proc.stdout.decode("utf-8"))
if hud["interrupt_level"] == "interrupt":
    ...  # 停止生成，应用 hud["control_levers"]
```

## Python 用法

```python
from stateprobe.skill import analyze_attention

hud = analyze_attention(user_context, agent_output)

# 跑偏概览（Phase 1~6）
print(hud.drift_level, hud.drift_score)
print(hud.next_turn_patch)

# 注意力到输出的控制层（Phase 7）
print(hud.interrupt_level)               # "ok" | "watch" | "interrupt"
for sig in hud.user_intent_map:
    print(sig.priority, sig.weight, sig.label)
for sig in hud.agent_attention_map:
    print(sig.alignment, sig.weight, sig.label)
if hud.output_trajectory:
    print(hud.output_trajectory.likely_direction,
          hud.output_trajectory.risk,
          hud.output_trajectory.confidence)
if hud.control_levers:
    print("boost:",      hud.control_levers.boost)
    print("return_to:",  hud.control_levers.return_to)
    print("suppress:",   hud.control_levers.suppress)
    print("stop_doing:", hud.control_levers.stop_doing)
```

`hud.to_dict()` 会返回可 JSON 序列化的对象，包含所有 Phase 7 字段。

Windows PowerShell 管道 JSON 时可能受 shell 编码影响。如果直接管道失败，优先用文件读写并显式指定 UTF-8，或者从 Python subprocess 调 CLI，保留原始 UTF-8 字节。

## HUD 字段

输出对象分两层。

### A 层：要求覆盖情况（Phase 1~6）

这些字段回答一个问题：用户每条要求有没有被 agent 输出体现出来？

- `core_focus`：agent 输出看起来主要在讲什么
- `reflected`：明确满足的用户要求
- `weak`：只弱弱碰到、没有充分展开的要求
- `ignored`：基本没覆盖的要求
- `violated`：违反了的“不要做什么”
- `drift_level`：`low`、`medium` 或 `high`
- `drift_score`：0 到 1 的跑偏分数
- `next_turn_patch`：下一轮可以直接用的纠偏建议
- `notes`：这个 HUD 能判断什么、不能判断什么

### B 层：注意力到输出的控制层（Phase 7）

这些字段把覆盖证据变成可见、可控制的 HUD。

- `user_intent_map`：用户到底想要什么。每项是 `IntentSignal(label, priority, weight, evidence)`，其中 `priority` 是 `must` / `must_not` / `supporting`，`weight` 归一化后总和约等于 1。
- `agent_attention_map`：agent 实际注意力集中在哪里。每项是 `AttentionSignal(label, weight, alignment, evidence)`，其中 `alignment` 包括：
  - `aligned`：命中必须满足的要求，而且输出里确实体现了
  - `partial`：碰到了必须满足的要求，但体现得弱
  - `off_task`：没有命中用户要求，方向偏了
  - `violation`：命中了用户明确不要的东西

- `attention_gaps`：用户要求和 agent 注意力之间的明确缺口。`kind` 是 `missing` / `under_focused` / `over_focused`。
- `output_trajectory`：如果继续这样写，大概率会往哪里偏。它是启发式判断，**不是真实下一 token 预测**。
- `control_levers`：下一轮怎么纠偏，包括 `boost`、`suppress`、`stop_doing`、`return_to`。
  - `boost` / `return_to`：把注意力拉回哪些用户要求
  - `suppress` / `stop_doing`：哪些方向要降低或停止
- `interrupt_level`：`"ok"` | `"watch"` | `"interrupt"`。
  - `ok`：可以继续
  - `watch`：可以写完当前段，但下一轮要纠偏
  - `interrupt`：现在就停，先应用 `control_levers` 再重启

## Agent 集成方式

host agent 可以在每次重要输出后跑一次 Skill：

1. 把用户当前要求保存为 `context`。
2. 把 agent 草稿或最终输出保存为 `output`。
3. 运行 `stateprobe skill overlay --json`。
4. 如果 drift 是 `medium` 或 `high`，把 `next_turn_patch` 注入下一轮。
5. 需要时把 HUD 展示给用户或审阅者。

推荐行为：

- 只在用户需要时展示 HUD。
- 把 `next_turn_patch` 当纠偏建议，不要当最终答案。
- 保留用户原始要求，不要偷偷改写。
- 不要把 Skill 层说成神经可解释性。

## 示例解读

如果用户说：

```text
核心是让 agent 的注意力可见。
不要把格式化当主线。
必须先做 Skill 再做企业线。
```

但 agent 主要回答 prompt 格式化和企业功能，HUD 应该显示：

- `drift_level` = `high`
- `interrupt_level` = `interrupt`
- `ignored`：agent 注意力可见这件事被忽略
- `weak` 或 `violated`：不要把格式化当主线这个约束被弱化或违反
- `agent_attention_map`：格式化 / 企业方向出现 `off_task` 或 `violation`
- `attention_gaps`：注意力可见这个要求出现 `kind=missing`
- `output_trajectory.likely_direction`：继续写会更偏向格式化 / 企业线
- `control_levers.return_to`：包含注意力可见这个要求
- `control_levers.stop_doing`：包含格式化这个方向
- `next_turn_patch`：把 Skill 和注意力 HUD 拉回中心

## 边界

这个 Skill 故意保持小而本地：

- 不调外部 API
- 不加载模型
- 不需要 GPU
- 不读取 hidden states
- 不实现 enterprise Runtime Probe

未来 Runtime Probe 线可能会读取 activations、vectors、logits 或 router traces。那是另一层，不要和这个 Skill 混在一起说。
