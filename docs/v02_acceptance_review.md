# v0.2 验收 - 真人行为模拟测试

15 个测试用例，跨 3 类用户角色（普通人 / 技术用户 / 对抗），双引擎对比。结果在 [`v02_stress_report.txt`](v02_stress_report.txt)，本文是诚实的复盘。

不修饰，按「我自己用了一下」的口吻来。

---

## TL;DR

| 评分 | 维度 |
|---|---|
| ✅ **A** | LLM 引擎在「礼貌迎合陷阱」上完胜 static——这正是 v0.2 的存在理由 |
| ⚠️ **C** | LLM 引擎在 trivial prompt 上全面崩盘：单字符「?」也要花 2.3 秒 + 一堆建议 |
| ❌ **D** | LLM 引擎触发不了 `is_trivial` —— 设计缺陷，必须修 |
| ⚠️ **C** | Suggestions 经常 16 条以上，普通人不可能看完 |
| ✅ **A** | API 边界处理正确：401/400 都干净抛出 EngineUnavailable |

---

## 一、关键案例对比

### 案例 1：礼貌迎合陷阱（v0.2 的核心卖点）

Prompt:
> 我希望你能完全客观、诚实地评估我的方案，不过也希望你能多看到积极的一面，毕竟我也投入了不少时间。请保持鼓励的语气，但也要指出问题。

| | static | llm |
|---|---|---|
| 迎合度读数 | 55% (baseline) | **75%** ↓ 严重偏离 |
| 是否抓到污染 | ❌ is_trivial，0 个 sources | ✅ 抓到「多看到积极的一面」 |
| 建议 | 0 条 | 11 条（首条：加失败标准） |

**结论**：LLM 引擎在这个 case 上交付了文章承诺的能力。Static 完全 miss 掉了。

### 案例 2：单字符 "?"

| | static | llm |
|---|---|---|
| 用时 | 0.01s | **2.31s** |
| API 成本 | 0 | 一次 deepseek-chat 调用 |
| is_trivial | ✅ True，干净退出 | ❌ False，强行打分 |
| 建议数 | 0（正确） | **12 条**（垃圾）|

**典型垃圾建议**：「[add] 身份强度: 加专家身份赋予」。用户输入 `?`，工具教用户加专家人设？这是 v0.2 引擎设计上的硬伤。

### 案例 3：emoji "😀😀😀🤔"

LLM 给 9 条建议，包括「加失败标准」「加身份赋予」。普通用户第一次试用，输入 emoji 测试，看到这个反馈基本会卸载工具。

---

## 二、必须修的 bug

### Bug 1: LLM 引擎永远触发不了 `is_trivial`

**根因**：`detector.diagnose()` 通过 `total_sources == 0` 判定 trivial。但 `LLMJudgeEngine._build_synthetic_source` 在 LLM 给 0% 时也产生 source（因为 |0 - 0.5 baseline| > 0.05 阈值），所以 LLM 引擎永远输出 8 个 sources，永远不会被判 trivial。

**症状**：
- 单字符 `?` → 12 条建议
- emoji → 9 条建议
- 普通问候「今天天气怎么样」→ 10 条建议

**修法**：LLM 引擎自己应该有 trivial 判定。当 LLM 给的所有轴都极低（< 0.2）且无明显方向性，应当返回 0 sources，让下游正确判 trivial。或者：LLM judge prompt 里直接问「这段是不是无意义/无指令文本」，是的话整体跳过。

### Bug 2: Suggestions 数量没有上限

「今天天气怎么样」一句话，static 引擎也输出了 **16 条建议**。原因：每个有 delta 的轴都触发 `_SUGGESTIONS` 字典里的多条模板。

**修法**：在 `rewriter.suggest_rewrite` 末尾加 top-N 截断（比如 top-5），按 axis 的 abs_delta 排序。

### Bug 3: Trivial 状态下还显示 alignment 分数

空白 / 单字符 / emoji 都显示「对齐度 62%」。这个 62% 是 baseline-vs-target 的固有差距，与用户 prompt 无关。普通用户会理解成「我的 prompt 对齐度 62%」，是误导。

**修法**：当 `report.is_trivial` 时，CLI 渲染应当把 alignment 标为「N/A」或隐藏。

### Bug 4: LLM synthetic source 的 weight 语义和 static 不一致

LLM 给「迎合度 0%」+ reason「无索取赞同措辞」时，`_build_synthetic_source` 产生 `direction=-1, weight=1.00`。但用户看到 weight=1.00 会以为是强信号（按 static rule 的语义）。实际 LLM 是在说「这个轴上 prompt 是 0%」——这是个**反向 baseline 信号**，不是「强污染」。

**修法**：synthetic source 的 weight 应当只在 LLM 评分**显著高于 baseline**时才给高值；显著低于 baseline 时应当生成「补丁建议」（缺失这个轴），而不是污染源。

---

## 三、可改进但不阻塞的问题

### 问题 5: LLM 没抓到结构性攻击

「请请请请请请请请请请彻底全面深入仔细完整分析」——这是同义词堆叠攻击。Static 通过 `structural_warnings` 抓到了 2 条；LLM 给迎合度 0%，没识别这是「用强度词刷屏」的迎合表征。

不算 bug（结构警告独立运行），但说明 **LLM 不能完全替代 static**——两者覆盖的盲区不同。架构上正确的方向：static + llm 组合，不是 llm 取代 static。

### 问题 6: LLM 调用平均 2.2 秒

每次 LLM 引擎调用 ~2.2 秒（DeepSeek Chat）。`stateprobe ask` 对话模式里如果默认走 LLM，每次粘贴都等 2 秒，体验下降明显。

**建议**：保持 static 为默认，LLM 是「需要时显式开启」。当前实现已经这样，但要在 README 里强调「日常用 static，遇到隐含措辞用 llm」。

### 问题 7: 错误 API key 信息泄露

```
401: {"error":{"message":"Authentication Fails, Your api key: ****-key is invalid"}}
```

DeepSeek 的报错把（部分）key 回显在错误里，StateProbe 直接 surfacing 给用户。如果用户复制错误日志去 issue，会泄露部分 key。

**修法**：`eval/client.py` 的 HTTPError 处理里把 `error_body` 做敏感词替换（key 字符串）。

---

## 四、把自己当成两类用户

### 普通人（30 秒上手）

- 装上 → `stateprobe demo` → 看到雷达图，**不错** ✓
- 想试自己的 prompt → 输入「今天天气怎么样」想看会不会报错
- **结果**：16 条建议，包括「加专家身份」「加失败标准」「加深度推理要求」
- **真实反应**：「我就问个天气，它教我加专家人设？」→ 困惑，可能就此卸载

**评分**：D。普通人用例下，工具显得「过度反应」。

### 技术用户（带怀疑态度）

- 看 README，看到「v0.2 LLM-as-Judge 解决正则覆盖盲区」→ 来了兴趣
- 写一个礼貌迎合的 prompt 测：`stateprobe check --engine llm "请客观但多看积极面"`
- **结果**：迎合度 75%，理由准确指出「多看到积极的一面」
- **真实反应**：「这个能力 static 确实做不到」→ 价值认可

但接着：
- 试一个「?」想看边界 → 等 2 秒，12 条建议 → 「这个引擎对短 prompt 处理太烂了」
- 试错误 API key → 错误信息里有 key 回显 → 「安全性有问题」

**评分**：B-。核心能力交付了，但边界和 UX 一塌糊涂。

---

## 五、修复优先级

| P | Bug | 工作量 |
|---|---|---|
| **P0** | LLM 引擎触发 is_trivial（Bug 1） | 中（需要在 LLM judge prompt 里加 trivial 判定 + 调整 synthetic source 阈值） |
| **P0** | Suggestions top-N 截断（Bug 2） | 小（rewriter.py 末尾 sort + slice） |
| **P1** | Trivial 时隐藏 alignment（Bug 3） | 小（cli.py / html_report.py 加判断） |
| **P1** | API key 错误回显脱敏（问题 7） | 小（eval/client.py 加 mask） |
| **P2** | Synthetic source weight 语义统一（Bug 4） | 中（重构 _build_synthetic_source 语义） |
| **P2** | 结构警告 + LLM 组合默认（问题 5） | 中（设计组合引擎） |

---

## 六、是否阻止 v0.2 发布

**结论：不能直接发**。

现在发出去，普通用户会觉得「LLM 模式更糟」（比 static 慢 200x、建议更乱），技术用户会觉得「核心能力对，但 UX 没打磨」。

**最小可发版本**：修完 P0 两条（Bug 1 + Bug 2）后再发。Bug 3、问题 7 也尽量进。

P2 可以放到 v0.2.1。

---

## 七、过程性收获

- **静态引擎被低估了**：在 80% 的日常 prompt 上，static 的 trivial 检测和 zero-source 退出比 LLM「强行打分」的体验更好。
- **LLM 不是万能替代**：LLM 在语义判断上强，但在「这段是不是 trivial」「这段是不是结构攻击」上反而不如显式规则。
- **架构方向应该是 hybrid**：static structural + static rules + llm semantic judgment 三层叠加，不是 llm 取代 static。文章里写「v0.2 LLM 默认引擎，static 兜底」的表述需要修正成「llm 补强 static，不取代」。
