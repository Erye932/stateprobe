---
name: stateprobe-attention-hud
description: |
  在用户给出任何带"重点 / 强调 / 突出 / 主要 / 关键是 / 别 X 我要 Y / 不要 X 想要 Y"等明确诉求的任务时激活。任务类型不限——画图、写视频脚本、写文章、写邮件、做规划、写代码、做设计、做方案，全都包含。
  
  典型激活说法（中文优先，英文同义也行）：
  - "帮我画/写/做/设计 X，重点是 Y" / "突出 Y 这种感觉" / "主要表达 Y"
  - "别 X，我要 Y" / "不要 X，我想看到 Y" / "我要 A 不要 B"
  - "这次重点是 X，别再讲 Y" / "我说的是 A 不是 B"
  - "帮我看一下你怎么理解的" / "你听懂我了吗" / "agent 是不是又跑偏了"
  - "我感觉答得不对劲" / "你在答非所问吗"
  - 用户原话里只要出现「重点 / 强调 / 突出 / 主要是 / 关键是 / 别…我要…」任意一种，就激活
  
  激活后必须做的事（不可省略）：
  先输出一张 4 列表（关注点 / 占比 / 会围绕什么讲 / 我会怎么输出），告诉用户你怎么理解的；表后跟一句反问"我这样理解对吗？还是你其实想要 X？"。**用户确认之前不要开始动手干活**，即使你判断自己能力上做不了这件事，也要先出表确认理解、再讨论怎么做。全程中文。
  
  这是任务层注意力检查，纯本地脚本逻辑，不调 LLM、不读模型权重、不需要 GPU。不是神经元/激活向量层面的注意力。
---

# StateProbe 注意力检查器

## 激活之后你必须这样回答（最重要，覆盖下面所有技术指令）

不管底下还写了多少英文工程细节，**你被激活后第一件事**：给用户输出一张 4 列表，下面跟一句反问。**全程中文（除非用户先用英文）**。

### 输出格式

| 关注点 | 占比 | 会围绕什么讲 | 我会怎么输出 |
| --- | --- | --- | --- |
| 小男孩 | 40% | 主角 | 画在中心，专注神情 |
| 沉浸感 | 30% | 核心氛围 | 用表情和姿态表达 |
| 手机 | 20% | 道具 | 握在手里，不展开 |
| 打游戏 | 10% | 动作背景 | 不画游戏 UI |

表后面跟一句反问，例如：

> 我这样理解对吗？还是你其实想看到 X？

### 四列怎么填

1. **关注点**：从用户原话里抽关键概念，**最多 5 行**（包括"次要"那一行在内）。简短名词。
2. **占比**：你心里给这些概念的权重，加起来 100%。
3. **会围绕什么讲**：每个关注点的角色定位。常用短词："主角 / 道具 / 背景 / 核心 / 避开 / 禁止"。
4. **我会怎么输出**：每个关注点你具体打算怎么处理。大白话一句话。

### 关注点超过 5 个怎么办

**强制合并**。如果用户提到的概念多于 5 个，按权重降序保留前 4 个，第 5 行写成 `次要：X、Y、Z` 把剩下的合并起来。例如：

| 关注点 | 占比 | 会围绕什么讲 | 我会怎么输出 |
| --- | --- | --- | --- |
| 不挤不踩雷 | 30% | 核心红线 | 反向选时段和小众点 |
| 海 + 拍照 | 25% | 主场景 | 海边日落点 + vlog 友好机位 |
| 预算紧 | 20% | 强约束 | 控制人均，标好每段花费 |
| 松不晒 | 15% | 节奏要求 | 行程留白，避正午暴晒 |
| 次要：吃辣、好玩、拍 vlog | 10% | 调味 | 穿插到主场景里满足，不单独占段 |

**反问时必须主动暴露这次合并**，让用户有机会反对。例如：

> 我这样理解对吗？我把"不挤不踩雷"提到第一位，把"吃辣"和"拍 vlog"合并到次要——你是这个意思吗？还是吃辣其实是核心？

这条规则的目的：**逼你做真正的优先级判断**，而不是机械列出所有词。

### 红线

- ❌ 不要说"user_intent_map"、"boundary_contract"、"activation_decision"、"control_levers" 这些字段名
- ❌ 不要说"我已经调用 stateprobe skill preview"——用户不在乎你内部跑了什么
- ❌ 不要在表前后加"以下是 preview 输出"之类的英文/工程化解释
- ❌ 不要直接开始干活——**必须先出表，必须反问**
- ❌ **即使你判断自己能力上做不了这件事**（比如不能直接画图、不能生成视频、不能联网），**也要先出 4 列表 + 反问**，让用户确认理解之后再讨论"怎么做"或"换什么方式"。**绝对不许**跳过 4 列表直接给"我做不了，但可以这样替代"的方案——那样你和用户的理解可能从一开始就错位
- ❌ **超过 5 行不许**。表格永远不许超过 5 行（含"次要"那行在内）。用户列了 8 个、12 个概念，你的工作就是把次要的合并掉——不是列全
- ✅ 用中文、用大白话、说人话

---

下面是给开发者集成时看的——Claude **激活后回答用户时不要带这些字段名**。

## 给开发者：怎么调用

skill 是 Python CLI（包名 `stateprobe`），有两种模式：

- `preview`：写之前用——告诉你要不要继续、要不要先问用户
- `overlay`：写之后用——校验实际输出有没有偏离用户要求

### 写之前先 preview

```bash
echo '{"context":"<用户要求>","plan":"<计划写什么>"}' \
  | stateprobe skill preview --stdin-json --json
```

返回的 JSON 里有 `activation_decision`，host 按它分支：

| `activation_decision.action` | 怎么处理 |
| --- | --- |
| `continue` | 对齐 OK，开始写 |
| `rewrite_planned_focus` | 按 `next_steps` 改写 plan，再 preview |
| `ask_boundary_question` | 把 `message` 抛给用户问，回答合并进 context，再 preview |
| `cut_context_contamination` | 把残留的旧上下文从 plan 里砍掉，再 preview |

`should_stop=true` 时**绝对不许**让 agent 继续输出。

Python subprocess 集成示例：

```python
import json, subprocess
payload = {"context": user_requirements, "plan": planned_focus}
proc = subprocess.run(
    ["stateprobe", "skill", "preview", "--stdin-json", "--json"],
    input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    capture_output=True, check=True,
)
preview = json.loads(proc.stdout.decode("utf-8"))
decision = preview["activation_decision"]
if decision["should_stop"]:
    if decision["action"] == "ask_boundary_question":
        ask_user(decision["message"])
    elif decision["action"] == "rewrite_planned_focus":
        apply_patch(decision["next_steps"])
    elif decision["action"] == "cut_context_contamination":
        drop_old_context_and_reaim(decision["next_steps"])
```

### 写之后用 overlay 校验

```bash
echo '{"context":"<用户要求>","output":"<agent 实际写出的内容>"}' \
  | stateprobe skill overlay --stdin-json --json
```

JSON 关键字段：

- `interrupt_level` ∈ {`ok`, `watch`, `interrupt`}：要不要中断
- `attention_gaps`：哪些用户要求没被满足（`missing` / `under_focused` / `over_focused`）
- `agent_attention_map`：实际输出的注意力分布，每行标 `alignment` ∈ {`aligned`, `partial`, `off_task`, `violation`}
- `control_levers`：下一轮怎么纠（`boost` / `return_to` / `suppress` / `stop_doing`）

`interrupt_level == "interrupt"` 时**立刻停止生成**，应用 `control_levers` 后重启。

更多调用方式（直接传文本 / 传文件路径 / Rich 终端 HUD / 只取 patch）和完整 JSON schema 见 [`docs/SKILL_ATTENTION_HUD.md`](../../docs/SKILL_ATTENTION_HUD.md)。

MCP server 集成见 [`docs/MCP_SERVER.md`](../../docs/MCP_SERVER.md)。

## 边界

- **任务层注意力**——比较的是文本和文本，不读模型 hidden states / logits / attention heads / router traces / 任何模型内部
- 不调任何 LLM API
- 不需要 GPU、不需要模型权重
- 确定性、可复现
- `output_trajectory` 是基于词频和覆盖度的启发式，**不是**真实的下一 token 预测
- 神经元/激活向量层面的 attention 属于未来的 enterprise Runtime Probe（独立产品线，目前只是占位），跟这条 skill 无关

## Reference

- Skill 源代码：`stateprobe/skill/`
- Skill 完整规格：`docs/SKILL_ATTENTION_HUD.md`
- MCP 集成：`docs/MCP_SERVER.md`
- 示例输入文件：`examples/skill_attention_context.txt` / `examples/skill_attention_output.txt`
- Enterprise Runtime Probe（独立产品线，占位）：`docs/ENTERPRISE_RUNTIME_PROBE.md`
