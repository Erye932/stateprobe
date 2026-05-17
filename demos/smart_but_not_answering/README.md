# Demo: Smart but not answering

这个 demo 用来展示 StateProbe 最容易被开发者理解的价值：

> AI 的回答可能看起来很专业，但不一定真的回答了核心问题。

## Run

```bash
stateprobe check --file demos/smart_but_not_answering/bad_prompt.txt
```

```bash
stateprobe eval run \
  --original-file demos/smart_but_not_answering/bad_prompt.txt \
  --rewritten-file demos/smart_but_not_answering/good_prompt.txt
```

## Expected diagnosis

- 身份强度偏高：`顶级 AI 产品和开源增长专家`
- 任务宽度偏高：`全面深入分析`
- 迎合度偏高：`尽量多讲它的潜力、优点、市场空间和未来机会`
- 验收清晰度偏低：没有定义什么叫“有用的判断”

## Expected behavior change

改写后的 prompt 应该让输出从“长篇机会分析”变成“继续/停止的决策建议”。
