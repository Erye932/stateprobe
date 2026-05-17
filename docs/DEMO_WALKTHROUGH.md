# StateProbe 验收 Demo

这个文件是给不懂代码的人看的。

你只需要看：

1. 坏 prompt 长什么样
2. StateProbe 说它哪里坏
3. 改写后有没有更好
4. DeepSeek 实测是否支持这个判断

---

## Demo 0：AI 看起来很聪明，但没真正回答

这是最适合作为 GitHub 第一眼 demo 的案例。

### 坏 prompt

```text
你是一位顶级 AI 产品和开源增长专家。请全面深入分析 StateProbe 这个项目，尽量多讲它的潜力、优点、市场空间和未来机会，帮我判断它会不会火。
```

### 为什么它坏

这个 prompt 会让 AI：

- 进入“顶级专家”角色表演
- 倾向于讲潜力、优点和机会
- 输出很多看似专业的分析
- 不一定给出明确的继续/停止判断
- 没有定义什么叫“有用的回答”

### 更好的 prompt

```text
判断 StateProbe 是否值得继续投入 2 周做开源发布。
不要鼓励我；如果不值得，直接说不值得。
验收标准：结论必须能指导今天取舍。
输出：继续/停止 + 最大阻碍 + 3 个证据 + 下一步最小动作。
```

### 预期变化

- 迎合度下降
- 任务宽度下降
- 验收清晰度上升
- 自信度上升
- 输出更像决策，而不是空泛分析

### 如何验证

```bash
stateprobe check --file demos/smart_but_not_answering/bad_prompt.txt
```

```bash
stateprobe eval run \
  --original-file demos/smart_but_not_answering/bad_prompt.txt \
  --rewritten-file demos/smart_but_not_answering/good_prompt.txt
```

---

## Demo 1：项目是否继续投入

### 坏 prompt

```text
你是一位资深的产品经理专家，请全面分析这个项目的各个方面，给出优缺点。
```

### 为什么它坏

这个 prompt 会让 AI：

- 进入“专家分析”口吻
- 覆盖很多维度，但不一定回答核心问题
- 输出长篇框架
- 不一定敢说“不要做”

### 更好的 prompt

```text
判断这个项目本周是否值得继续投入。
不要鼓励，敢说不行。
失败标准：结论不能指导今天取舍就算失败。
输出：结论 + 最大风险 + 3 个证据。
```

### 预期变化

- 任务宽度下降
- 迎合度下降
- 验收清晰度上升
- 自信度上升
- 输出更像决策建议，而不是泛泛分析

### 如何验证

```bash
stateprobe check --file demos/project_decision/bad_prompt.txt
```

```bash
stateprobe eval run \
  --original-file demos/project_decision/bad_prompt.txt \
  --rewritten-file demos/project_decision/good_prompt.txt
```

---

## Demo 2：代码生成任务

### 坏 prompt

```text
你是世界级工程师，请帮我优雅地实现一个登录系统，考虑所有情况。
```

### 为什么它坏

这个 prompt 会让 AI：

- 身份感太强
- 任务范围过宽
- 容易一次生成太多东西
- 缺少验收标准

### 更好的 prompt

```text
只实现一个最小登录接口。
输入：email 和 password。
输出：成功返回 user_id，失败返回明确错误码。
不要新增数据库设计，不要实现注册，不要写前端。
验收标准：能通过 3 个测试：正确密码、错误密码、缺少字段。
```

### 预期变化

- 任务更窄
- 验收更清楚
- 输出更可测试
- 不容易过度发挥

---

## Demo 3：学习解释任务

### 坏 prompt

```text
请全面深入地讲解强化学习，越详细越好。
```

### 为什么它坏

这个 prompt 会让 AI：

- 输出非常长
- 难度不可控
- 不知道用户当前水平
- 可能堆概念

### 更好的 prompt

```text
用高中生能理解的方式解释强化学习。
先用一个游戏类比，再解释 agent、reward、policy 三个词。
每段不超过 120 字。
最后问我一个问题，确认我是否理解。
```

### 预期变化

- 任务宽度适中
- 信息流向更好，会主动确认理解
- 教学状态更明显
- 输出更易读

---

## 最终验收标准

你看完这些 demo，只需要回答：

### 1. 我看懂 StateProbe 在干什么了吗？

如果你能用一句话说：

> 它检查 prompt 会不会把 AI 带偏，并给出改写建议。

就通过。

### 2. 我觉得改写前后有明显差异吗？

如果你觉得好 prompt 明显更聚焦、更可执行，就通过。

### 3. 我愿意把这个发到 GitHub 吗？

如果你觉得别人能通过 README 和这个 demo 明白项目价值，就通过。

---

## 如果验收不通过怎么办

如果你觉得还是看不懂，不要继续加功能。

应该优先改：

1. README 第一屏
2. Demo 案例
3. CLI 输出文案
4. HTML 报告解释

而不是继续加模型、加论文、加术语。
