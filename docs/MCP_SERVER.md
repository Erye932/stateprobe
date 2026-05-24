# StateProbe MCP Server

StateProbe 提供一个可选的 MCP server，让 Claude Code、Cursor、Cline、Continue 这类 agent host 可以把 StateProbe 当成本地工具调用。

它的定位很简单：**agent 正式输出之前，先跑一次外部控制检查，判断该继续、重写、追问用户，还是切断旧上下文。**

MCP server 暴露两个工具：

- `stateprobe_preview_attention(context: str, planned_focus: str) -> dict`
- `stateprobe_overlay_attention(context: str, output: str) -> dict`

`stateprobe_preview_attention` 是主入口。写正文、画图、生成视频、做方案之前先调它。它会对比“用户真正要什么”和“agent 准备关注什么”，然后返回 `activation_decision`。

对画图 / 视频生成任务，它还会告诉 host：

- 哪些东西必须直接出现
- 哪些东西只能用姿态、氛围、构图暗示
- 哪些东西不该出现
- 哪些词可能被模型字面化成多余 UI、文字或符号
- 生成前要不要先问用户一句

`stateprobe_overlay_attention` 是输出后的复盘入口。agent 写完之后调它，用来检查实际输出有没有跑偏。

两个 MCP 工具分别等价于 CLI：

```bash
stateprobe skill preview --stdin-json --json
stateprobe skill overlay --stdin-json --json
```

## 安装

本地仓库安装：

```bash
pip install -e ".[mcp]"
```

包安装：

```bash
pip install "stateprobe[mcp]"
```

`[mcp]` 会安装官方 MCP Python SDK。StateProbe 本身仍然是本地优先：不调 LLM API、不加载模型、不需要 GPU。

## 直接运行

```bash
stateprobe-mcp
```

这会启动一个 stdio MCP server，等待 MCP client 连接，不会打印普通 CLI 报告。

也可以直接跑模块：

```bash
python -m stateprobe.mcp_server
```

## 工具协议

### Preview 输入

```json
{
  "context": "用户当前要求、重点、不要做什么。",
  "planned_focus": "agent 正式输出前，准备围绕什么写。"
}
```

### Overlay 输入

```json
{
  "context": "用户当前要求、重点、不要做什么。",
  "output": "agent 已经写出的回复或草稿。"
}
```

所有字段都必须是非空字符串。

### Preview 输出

`stateprobe_preview_attention` 返回：

- `risk_level`
- `risk_score`
- `should_continue`
- `user_intent_map`
- `planned_attention_map`
- `missing_before_start`
- `control_levers`
- `opening_patch`
- `boundary_decomposition`
- `literalization_risks`
- `boundary_questions`
- `context_contamination_risks`
- `activation_decision`
- `notes`

其中最重要的是 `activation_decision`。host 不需要自己从一堆字段里猜下一步，直接按这个字段分支。

`activation_decision` 包含：

- `action`：下一步动作，取值是 `continue`、`continue_with_warning`、`rewrite_planned_focus`、`ask_boundary_question`、`cut_context_contamination`
- `should_stop`：如果是 `true`，host 不应该让 agent 继续输出用户可见内容
- `confidence`：决策有多确定，`low` / `medium` / `high`。**只有 `high` 会送出 hard stop**；证据不够强时会自动降级为 `continue_with_warning`
- `reason`：为什么要这么做
- `message`：可以展示给用户或 agent 的一句话
- `blockers`：触发停止/警告的原因标签，比如 `high_preview_risk`、`boundary_question`、`context_contamination`、`attention_warning`
- `evidence`：决策所依据的具体证据——用户哪条要求、plan 哪里漏了、上下文哪段被旧任务污染了
- `next_steps`：恢复输出前应该执行的修正步骤

五种 `action` 的意思：

| action | host 应该怎么做 |
|---|---|
| `continue` | 理解基本对齐，可以继续输出 |
| `continue_with_warning` | 不要打断工作流；把 `evidence` 暴露给用户/agent，让他们自己决定是否调整 |
| `rewrite_planned_focus` | 先别输出，按 `next_steps` 重写计划，再跑一次 preview |
| `ask_boundary_question` | 先把 `message` 问给用户，合并回答后再继续 |
| `cut_context_contamination` | 先删掉旧上下文残留，重新对准用户最新要求 |

> StateProbe Skill 不是 oracle。硬拦只在 `confidence=high` 且有具体 `evidence` 时触发；证据不够强的风险会走 `continue_with_warning` 路径，让 host 看到 evidence 但不会被中断。

### Overlay 输出

`stateprobe_overlay_attention` 返回：

- `drift_level`
- `drift_score`
- `interrupt_level` — `ok` / `watch` / `interrupt`
- `interrupt_confidence` — `low` / `medium` / `high`. Mirrors the
  preview-side `activation_decision.confidence`. Only `high` + a
  non-empty `interrupt_evidence` produces `interrupt`; weaker signals
  downgrade to `watch`.
- `interrupt_evidence` — list of human-readable reasons backing the
  verdict. Hosts should display these to the user instead of treating
  `interrupt` as an oracle.
- `user_intent_map`
- `agent_attention_map`
- `attention_gaps`
- `output_trajectory`
- `control_levers`
- `reflected`
- `weak`
- `ignored`
- `violated`
- `next_turn_patch`
- `notes`

## Claude Desktop / Claude Code 配置

安装 `stateprobe[mcp]` 后，可以直接用 `stateprobe-mcp`：

```json
{
  "mcpServers": {
    "stateprobe": {
      "command": "stateprobe-mcp",
      "args": []
    }
  }
}
```

如果是本地仓库、没有安装 console script，可以用 Python 模块方式：

```json
{
  "mcpServers": {
    "stateprobe": {
      "command": "python",
      "args": ["-m", "stateprobe.mcp_server"],
      "cwd": "/absolute/path/to/stateprobe"
    }
  }
}
```

Windows 上 `cwd` 用绝对路径，例如：

```json
{
  "mcpServers": {
    "stateprobe": {
      "command": "python",
      "args": ["-m", "stateprobe.mcp_server"],
      "cwd": "D:\\projects\\stateprobe"
    }
  }
}
```

## Cursor 配置

Cursor 可以在 MCP 设置里加 server：

```json
{
  "mcpServers": {
    "stateprobe": {
      "command": "stateprobe-mcp",
      "args": []
    }
  }
}
```

如果 `stateprobe-mcp` 不在 PATH 里，就用 Python 模块方式，并写上 `cwd`：

```json
{
  "mcpServers": {
    "stateprobe": {
      "command": "python",
      "args": ["-m", "stateprobe.mcp_server"],
      "cwd": "D:\\projects\\stateprobe"
    }
  }
}
```

## 激活协议

Agent host 应该把 StateProbe 当成“写之前先检查”的外部控制层，而不是手动报告生成器。

遇到这些情况，host 应该在输出前调用 `stateprobe_preview_attention`：

- 用户明确说了重点、验收标准、不要做什么
- 用户要画图、生成视频、做视觉设计、分镜、创意方向
- 下一步成本高、难撤回，或者很依赖视觉细节
- agent 准备替用户做一个用户没确认过的解释选择
- 对话里已经出现“不是这个”“你漏了”“重点是”“不要”这类纠偏

host 应该把 `planned_focus` 写成一句短话：agent 准备围绕什么输出。不要把最终答案塞进 `planned_focus`，这里要传的是“输出前的打算”。

推荐流程：

1. 把用户当前要求整理成 `context`。
2. 让 agent 写一句短的 `planned_focus`。
3. 调用 `stateprobe_preview_attention`。
4. 读取 `activation_decision.action`。
5. 如果是 `continue`，继续输出。
6. 如果是 `rewrite_planned_focus`，按 `next_steps` 重写计划，再跑一次 preview。
7. 如果是 `ask_boundary_question`，把 `message` 问给用户，合并回答后再继续。
8. 如果是 `cut_context_contamination`，先删掉旧上下文残留，再重新 preview。
9. 只要 `activation_decision.should_stop` 是 `true`，就不要让 agent 输出用户可见内容。
10. 不要把这一层说成神经可解释性；它是任务层文本控制。

最小 host 指令：

```text
在正式回答、画图、生成视频之前，调用 StateProbe 的 stateprobe_preview_attention。
传入用户当前要求和你的 planned_focus。
读取 activation_decision.action，并按 next_steps 执行。
activation_decision.should_stop 为 true 时，不要输出用户可见内容。
```

## 输出后的推荐行为

使用 MCP 工具时，host agent 可以在输出后这样做：

1. 把用户当前要求收成 `context`。
2. 把 agent 草稿或刚发出的回复收成 `output`。
3. 调用 `stateprobe_overlay_attention`。
4. 如果 `interrupt_level == "interrupt"` 且 `interrupt_confidence == "high"`，停止当前方向，把 `interrupt_evidence` 透传给用户，再应用 `control_levers` 重启。
5. 如果 `interrupt_level == "watch"`（包括 `interrupt_confidence` 是 `medium` / `low` 时被自动降级的情况），写完当前句或当前段后，应用 `boost` / `return_to`，把 `interrupt_evidence` 作为软提示展示，但不要硬停。
6. 不要把这一层说成神经可解释性；它是任务层文本控制。

## 边界

MCP server 只是 `stateprobe.skill.preview_attention` 和 `stateprobe.skill.analyze_attention` 的薄封装。

它不会：

- 读取 hidden states、logits、attention heads 或 router traces
- 调外部 API
- 要 API key
- 要 GPU
- 修改项目文件
- 替代未来的 enterprise Runtime Probe 线
