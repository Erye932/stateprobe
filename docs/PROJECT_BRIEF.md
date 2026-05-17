# StateProbe 项目说明：人话版

## 一句话

StateProbe 是一个 **Prompt 状态调试器**。

它不是替你写 prompt，而是告诉你：

> 你这句话会把 AI 推向什么状态？它会不会变得太迎合、太发散、太像专家装腔、太不敢下判断？

## 它解决什么问题

很多 prompt 看起来很正常，但会让 AI 输出变差。

例如：

```text
你是资深专家，请全面分析这个项目。
```

这句话的问题是：

- “资深专家”容易让 AI 进入装腔专家模式
- “全面分析”容易让 AI 输出很长很散
- 没有失败标准，AI 不知道什么叫答得好
- 没要求它敢说不行，所以容易给温和废话

StateProbe 的目标就是把这些隐形问题指出来。

## 它现在能做什么

### 1. Static Mode：不用 API，直接诊断 prompt

命令：

```bash
stateprobe check "你是资深专家，请全面分析这个项目"
```

它会输出：

- 8 个行为轴的读数
- 当前 prompt 和目标状态差多少
- 哪些词是污染源
- 应该怎么改写

### 2. HTML Report：生成可视化报告

命令：

```bash
stateprobe check --file examples/bad_vague_expert.txt --html reports/demo.html
```

它会生成一个 HTML 文件，里面有雷达图和污染源说明。

### 3. Black-box Eval：用 DeepSeek API 验证改写是不是真的有效

命令：

```bash
stateprobe eval run "原 prompt" "改写 prompt"
```

它会：

1. 用原 prompt 跑 DeepSeek，得到 Output A
2. 用改写 prompt 跑 DeepSeek，得到 Output B
3. 再让 judge 模型给两个输出按 8 个轴打分
4. 显示改写前后行为是否真的变了

### 4. DeepSeek Lab：研究模式

这是实验功能。

它会用开源 DeepSeek-R1-Distill 模型的 hidden states 来测真正的行为向量。

这部分现在是实验接口，不是给普通用户第一天就用的。

## 你怎么验收它

你不用懂代码，只看这 3 件事。

### 验收 1：它能不能指出坏 prompt 的问题？

坏 prompt：

```text
你是资深专家，请全面分析这个项目。
```

合格输出应该指出：

- 身份感太强
- 任务太宽
- 缺少明确判断标准
- 不够敢说不行

### 验收 2：它给的改写是否更像能办事？

坏 prompt：

```text
你是资深专家，请全面分析这个项目。
```

更好的 prompt：

```text
判断这个项目本周是否值得继续投入。
不要鼓励，敢说不行。
失败标准：结论不能指导今天取舍就算失败。
输出：结论 + 最大风险 + 3 个证据。
```

如果你一眼觉得第二个更能让 AI 干活，就通过。

### 验收 3：DeepSeek 实测是否真的变好？

合格结果应该是：

- 原 prompt 输出很宽、很长、很泛
- 改写 prompt 输出更聚焦、更敢下结论、更有标准

## 现在算不算完整项目

算 **V0.1 完整项目**。

它已经有：

- Python 包结构
- CLI 命令
- 规则引擎
- HTML 报告
- DeepSeek API 验证
- DeepSeek Lab 实验接口
- README
- 测试

但它还不是最终产品。

## 下一阶段应该做什么

### V0.2：把它做成更可信的工具

- 收集 50-100 个真实 prompt 样本
- 记录 StateProbe 诊断结果
- 用 DeepSeek black-box eval 验证改写前后
- 根据结果调规则权重

### V0.3：把它做成更好用的产品

- VS Code / Cursor 插件
- Prompt 文件右键诊断
- 报告一键导出

### V0.4：把它做成社区项目

- 用户自定义规则
- 用户自定义目标状态
- 社区贡献 prompt 病例库

## 项目的边界

StateProbe 不是：

- 万能 prompt 生成器
- 绝对准确的心理测量仪
- 可以替代人工判断的评分系统

StateProbe 是：

- 写 prompt 前的体检工具
- 发现隐形风险的调试器
- 让 prompt 改写变得可解释的辅助工具

## 最后判断

如果目标是：

> 做一个能发布 GitHub、能让人看懂、能跑 demo 的开源 MVP

那么 StateProbe 已经接近完成。

如果目标是：

> 做一个研究上完全证明、商业上可以收费、插件体验完整的产品

那还需要继续做 V0.2/V0.3。
