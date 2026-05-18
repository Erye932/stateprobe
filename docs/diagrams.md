# StateProbe 架构图集（v0.2 hybrid）

四张关键图，用于知乎 / 微信 / X 文章。Mermaid 源码可直接在知乎 / GitHub 渲染；
也提供 ASCII fallback 供平台不支持 Mermaid 时使用。

**PNG 已生成在 `docs/images/diagram_NN_*.png`**（用 `python scripts/export_diagrams.py`
通过 mermaid.ink API 自动导出）。修改了下面任何一个 mermaid 块后，重跑该脚本即可。

---

## 图 1：四层 hybrid 架构总图

**用途**: 文章第五章核心架构图。一图说清「证据流向」。

```mermaid
flowchart TB
    P([Prompt])

    subgraph L1["Layer 1 · 结构警告"]
        S[长度 / 重复 /<br/>同义词堆叠]
    end

    subgraph L2["Layer 2 · Evidence Contributors（并行）"]
        direction LR
        SC[StaticRule<br/>conf=1.0<br/>始终运行]
        LC[LLMJudge<br/>conf∈0~1<br/>--llm-augment]
        EC["EmbeddingContributor<br/>(v0.3 规划)"]
        LB["LabContributor<br/>(v0.4 规划)"]
    end

    POOL[("合并证据池<br/>Dict[Axis, List[PollutionSource]]")]

    subgraph L3["Layer 3 · Aggregator（唯一聚合器）"]
        AG[过滤 conf < 0.30<br/>per-axis<br/>tanh Σ dir × w × conf<br/>+ baseline]
    end

    subgraph L4["Layer 4 · Reasoner"]
        R1[compute_deltas]
        R2[suggest_rewrite top-N]
        R3[detect_overlaps]
    end

    REP([Report])

    P --> L1
    P --> SC
    P --> LC
    P --> EC
    P --> LB
    SC --> POOL
    LC --> POOL
    EC -.-> POOL
    LB -.-> POOL
    POOL --> AG
    AG --> R1
    AG --> R2
    AG --> R3
    L1 --> REP
    R1 --> REP
    R2 --> REP
    R3 --> REP

    style L2 fill:#f0f7ff,stroke:#4a90e2
    style L3 fill:#fff5e6,stroke:#e29c4a
    style POOL fill:#e8f5e9,stroke:#43a047
    style EC stroke-dasharray: 5 5
    style LB stroke-dasharray: 5 5
```

**ASCII fallback**:

```
                       prompt
                          |
                          v
   +----------------------+----------------------+
   |    Layer 1 结构警告（always-on）             |
   |    长度 / 重复 / 同义词堆叠                  |
   +----------------------+----------------------+
                          |
   +----------------------v----------------------+
   |    Layer 2 Evidence Contributors（并行）     |
   |  +--------+  +--------+  +-------+  +-----+ |
   |  | Static |  | LLM    |  | Embed |  | Lab | |
   |  | conf=1 |  | conf=? |  | (v.3) |  |(v.4)| |
   |  +---+----+  +----+---+  +---+---+  +--+--+ |
   +------|------------|----------|---------|----+
          |            |          |         |
          v            v          v         v
        +----------- 合并证据池 -----------+
        | Dict[Axis, List[PollutionSource]]|
        +-----------------+-----------------+
                          |
   +----------------------v----------------------+
   |    Layer 3 Aggregator（唯一聚合器）          |
   |    1. 过滤 confidence < 0.30                |
   |    2. per-axis tanh(Σ dir × w × conf)       |
   |    3. anchor at baseline                    |
   +----------------------+----------------------+
                          |
   +----------------------v----------------------+
   |    Layer 4 Reasoner（纯函数）                |
   |    deltas + suggestions(top-N) + overlaps   |
   +----------------------+----------------------+
                          |
                          v
                       Report
```

---

## 图 2：v0.2.0.dev0 错误架构 vs v0.2 正确架构

**用途**: 文章第四章「弯路复盘」对比图。一眼看出区别。

```mermaid
flowchart LR
    subgraph WRONG["v0.2.0.dev0 ❌ 二选一"]
        direction TB
        P1([Prompt])
        SW{"--engine = ?"}
        SE[StaticEngine<br/>regex only]
        LE[LLMJudgeEngine<br/>LLM only]
        R1([Reading])
        P1 --> SW
        SW -->|static| SE
        SW -->|llm| LE
        SE --> R1
        LE --> R1
        style SE stroke:#d9534f
        style LE stroke:#d9534f
    end

    subgraph RIGHT["v0.2 ✅ 证据合并"]
        direction TB
        P2([Prompt])
        SC2[StaticRule<br/>Contributor]
        LC2[LLMJudge<br/>Contributor]
        POOL2[("证据池")]
        AG2[Aggregator]
        R2([Reading])
        P2 --> SC2
        P2 --> LC2
        SC2 --> POOL2
        LC2 --> POOL2
        POOL2 --> AG2
        AG2 --> R2
        style SC2 stroke:#5cb85c
        style LC2 stroke:#5cb85c
    end

    WRONG -.->|"问题: 静态盲区<br/>or LLM 幻觉，<br/>用户选一种"| RIGHT
```

**ASCII fallback**:

```
v0.2.0.dev0 ❌ 二选一               v0.2 ✅ 证据合并
                                  
prompt                              prompt
   |                                   |
   v                                   |--> StaticRule -+
--engine = ?                          |--> LLMJudge   -|
   |                                                   v
   |--> StaticEngine ----+                       证据池
   `--> LLMJudgeEngine --+                            |
                         |                            v
                         v                       Aggregator
                      Reading                         |
                                                      v
问题：每个引擎都有盲区               Reading（两层叠加）
       用户在盲区里二选一            优势：所有证据合并，trivial 不丢
```

---

## 图 3：礼貌迎合陷阱的诊断对比

**用途**: 文章核心 demo 视觉化。展示 hybrid 的实际价值。

```mermaid
flowchart TB
    PROMPT["📝 Prompt:<br/>「我希望你能完全客观地评估，<br/>不过也希望你多看到积极的一面，<br/>毕竟我也投入了不少时间」"]

    subgraph ST["仅静态规则"]
        SR["扫描已知关键词<br/>「全面」「专家」「step by step」"]
        S0["❌ 0 条污染源<br/>报告：未检测到反模式"]
    end

    subgraph HY["Hybrid：static + LLM"]
        HR["扫描 + LLM 语义理解"]
        H1["✅ [LLM] 迎合度 +0.70 conf=0.90<br/>matched: 「多看到积极的一面」"]
        H2["✅ [LLM] 验收清晰度 +0.40 conf=0.70<br/>matched: 「完全客观、诚实地评估」"]
        H3["📋 Top 改写建议:<br/>1. 删除迎合诱导词<br/>2. 加显式失败标准"]
    end

    PROMPT --> SR
    PROMPT --> HR
    SR --> S0
    HR --> H1
    HR --> H2
    HR --> H3

    style ST fill:#fce8e6,stroke:#d9534f
    style HY fill:#e6f4ea,stroke:#5cb85c
```

---

## 图 4：v0.2 → v0.4 战略升级路径

**用途**: 文章路线图章节。说明现在做的是 lint，未来做的是 X-ray。

```mermaid
flowchart LR
    subgraph NOW["现在 · v0.2 lint"]
        N1[输入 Prompt]
        N2[文本特征分析<br/>正则 + LLM 语义]
        N3[告诉你<br/>「激活了哪些方向」]
        N1 --> N2 --> N3
    end

    subgraph SOON["1-2 月 · v0.3 校准"]
        S1[公开 benchmark]
        S2[嵌入模型离线兜底]
        S3[VS Code 插件]
    end

    subgraph DIFF["3-6 月 · v0.4-0.5 X-ray<br/>真正的护城河"]
        D1[读 DeepSeek MoE 专家路由]
        D2[抽出命名情绪向量库]
        D3[Steering API<br/>「让你精确控制激活」]
        D1 --> D2 --> D3
    end

    NOW ==> SOON ==> DIFF

    style NOW fill:#eef
    style SOON fill:#efe
    style DIFF fill:#ffe,stroke:#e29c4a,stroke-width:3px
```

**关键文案（图下面写一行）**:

> 阶段 1（lint）：占住「prompt 体检」心智位，积累用户和数据。
> 阶段 2（X-ray）：用 DeepSeek MoE 开源权重做真实激活内省——OpenAI / Claude 物理上做不到的事。

---

## 渲染清单

| 图 | 文件 | 用途 |
|---|---|---|
| 图 1 | `docs/images/diagram_01_hybrid_pipeline.png` | 知乎 v2 §5 核心架构 |
| 图 2 | `docs/images/diagram_02_wrong_vs_right_arch.png` | 知乎 v2 §4 弯路复盘 / X 短帖配图 |
| 图 3 | `docs/images/diagram_03_polite_sycophancy_demo.png` | 知乎 v2 §5 末尾 demo / 小红书封面 |
| 图 4 | `docs/images/diagram_04_v02_to_v04_roadmap.png` | 知乎 v2 §9 路线图 / X 路线图帖 |

重新导出（修改了 mermaid 源码后）：

```bash
python scripts/export_diagrams.py
```

脚本会调用 https://mermaid.ink API（无需安装任何 Node 工具链），带重试和稳定的英文 slug 命名。
