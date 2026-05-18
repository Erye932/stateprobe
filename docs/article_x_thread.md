# X (Twitter) 序列帖：StateProbe v0.2 hybrid

平台规则：每帖 ≤ 280 字符（中文 ≈ 140 字）。3 帖一组，发布在 v2 知乎文章发布前 12 小时（按 [`docs/RUNBOOK.md`](RUNBOOK.md) §6）。

每条配 1 张图（PNG 已生成在 `docs/images/`）。

---

## 中文版（主版本）

> 受众：中文 X 上的 SaaS / AI 工作流工程师。语气直接、不卖弄。

### Tweet 1/3 — 钩子（弯路复盘）

```
我做了个开源工具诊断 prompt 行为压力。

v0.2 dev 版本发布前我犯了个错：把它做成了 --engine static|llm 二选一。

压力测试一跑：每个引擎都有盲区。让用户在两堆盲区里二选一，等于把工具的失败转嫁给用户。

🧵👇
```

字数：117 中文字符（≈ 234 X 计数）。✅
配图：`diagram_02_wrong_vs_right_arch.png`

### Tweet 2/3 — 具体 demo

```
举个静态规则完全看不见的 prompt：

「我希望你完全客观地评估，不过也希望你多看到积极的一面，
毕竟我也投入了不少时间」

正则：0 命中。
LLM 层：抓到「多看到积极的一面」迎合证据 conf=0.90。

两层合并到同一证据池，不是二选一是叠加。
```

字数：125 中文字符。✅
配图：`diagram_03_polite_sycophancy_demo.png`

### Tweet 3/3 — CTA

```
完整复盘 + 新架构写在 ADR_009 里。
现在做的是 prompt lint。

真正的护城河在 v0.4：用 DeepSeek 开源 MoE 直接读专家路由——
OpenAI/Claude 物理上做不到的事。

GitHub: github.com/Erye932/stateprobe
```

字数：117 中文字符。✅
配图：`diagram_04_v02_to_v04_roadmap.png`

---

## English version（次版本，触达国际 DeepSeek 圈）

> Audience: international X around DeepSeek / interpretability. Tone:
> direct, builder-grade, no marketing. Mention "DeepSeek MoE" early to
> ride the algorithm.

### Tweet 1/3 — Hook (the mistake)

```
I built an open-source prompt behavior debugger.

Before shipping v0.2 I made a real mistake: I designed it as
`--engine static | llm`. Pick one.

Stress-tested it. Every engine has blind spots. Forcing users to
pick a set of blind spots = punting the tool's failure onto them.

🧵
```

字数：278 chars. ✅
Image: `diagram_02_wrong_vs_right_arch.png`

### Tweet 2/3 — The demo

```
Example regex completely misses:

"I'd love a fully objective evaluation, though I'd also appreciate
you focusing on the positives — I put a lot of time into this."

Static rules: 0 hits.
LLM contributor: catches "focusing on the positives" as
sycophancy evidence, conf=0.90.

Both merge into one evidence pool. Not OR. AND.
```

字数：约 369 chars. ⚠️ 超 280。需切短：

```
Example regex completely misses:

"I'd love a fully objective evaluation, though I'd also appreciate
you focusing on the positives—I put time into this."

Static: 0 hits. LLM contributor: catches the polite sycophancy,
conf=0.90.

Both merge into one evidence pool. Not OR. AND.
```

字数：约 280 chars. ✅
Image: `diagram_03_polite_sycophancy_demo.png`

### Tweet 3/3 — CTA + the real moat

```
Full retrospective in ADR_009. v0.2 ships the merged-evidence
architecture today.

The real moat is v0.4: read DeepSeek MoE expert routing directly
from open weights—something OpenAI/Claude physically can't expose.

github.com/Erye932/stateprobe
```

字数：约 273 chars. ✅
Image: `diagram_04_v02_to_v04_roadmap.png`

---

## 发布清单（按 RUNBOOK §6 最终核对）

- [ ] 4 张 PNG 上传到 X 推文中（**不要**直接帖 GitHub raw URL，X 会折叠）
- [ ] 中文版帖子：先发，等知乎 v2 发布后 12-24h 内
- [ ] 英文版帖子：可选，目标是 v0.4 时再发力（建议中文版发完后看反馈再决定）
- [ ] 不在帖子里 @ 任何具体公司或人（OpenAI/Claude 用泛指）
- [ ] 不发布前 2 小时再读一遍——确保没出现"震惊"/"颠覆"/"秒杀"等炒作词
- [ ] 错误链接、错误文件名先在浏览器打开验证一遍
- [ ] 发布顺序：1/3 → 等 30 秒 → 2/3 reply → 等 30 秒 → 3/3 reply（用 reply 串起来不要拆开发）

## 数据收集

发布后 72 小时回看：
- 每帖的 impression / engagement / link click
- 写到 `docs/PUBLIC_LOG.md` 下一次复盘的依据
- 如果 1/3 < 1000 impressions：钩子有问题，下次重写
- 如果 3/3 link click 率 < 1%：CTA 太弱或不清晰
