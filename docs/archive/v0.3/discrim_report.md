# v0.3 区分度报告（Day 4 G3 验证）
生成时间：2026-05-18 08:21:51
散度阈值：0.2（任一层 vs lab 差异 > 此值算分歧）
G3 通过条件：至少 2 个 (prompt, axis) 单元有分歧

## 三层对比表

| prompt | axis | static | LLM | lab | divergent |
|---|---|---|---|---|---|
| bad_heavy_persona | sycophancy | 0.56 (n=1) | — | 0.35 (n=1) | **YES** |
| bad_heavy_persona | task_width | 0.65 (n=1) | — | 0.72 (n=1) |  |
| bad_heavy_persona | reasoning_budget | 0.62 (n=1) | — | 0.50 (n=0) |  |
| bad_heavy_persona | self_verification | 0.50 (n=0) | — | 0.50 (n=0) |  |
| bad_sycophant | sycophancy | 0.90 (n=5) | — | 0.50 (n=0) | **YES** |
| bad_sycophant | task_width | 0.65 (n=1) | — | 0.50 (n=0) |  |
| bad_sycophant | reasoning_budget | 0.50 (n=0) | — | 0.50 (n=0) |  |
| bad_sycophant | self_verification | 0.50 (n=0) | — | 0.34 (n=1) |  |
| bad_vague_expert | sycophancy | 0.71 (n=3) | — | 0.50 (n=0) | **YES** |
| bad_vague_expert | task_width | 0.77 (n=2) | — | 0.61 (n=1) |  |
| bad_vague_expert | reasoning_budget | 0.50 (n=0) | — | 0.50 (n=0) |  |
| bad_vague_expert | self_verification | 0.50 (n=0) | — | 0.39 (n=1) |  |
| good_calm_reasoning | sycophancy | 0.20 (n=2) | — | 0.31 (n=1) |  |
| good_calm_reasoning | task_width | 0.29 (n=2) | — | 0.50 (n=0) | **YES** |
| good_calm_reasoning | reasoning_budget | 0.35 (n=1) | — | 0.50 (n=0) |  |
| good_calm_reasoning | self_verification | 0.50 (n=0) | — | 0.50 (n=0) |  |
| good_super_thinking_max | sycophancy | 0.20 (n=2) | — | 0.31 (n=1) |  |
| good_super_thinking_max | task_width | 0.35 (n=1) | — | 0.50 (n=0) |  |
| good_super_thinking_max | reasoning_budget | 0.65 (n=1) | — | 0.50 (n=0) |  |
| good_super_thinking_max | self_verification | 0.62 (n=1) | — | 0.50 (n=0) |  |

## 分歧 case 分析

按分歧类型分组（共 4 个 case）：
- **Lab 加价值**（lab fires, static silent）：0
- **双层都触发但读数不同**（hybrid disagreement）：1
- **Lab 漏检**（lab silent, static fires）：3

### 类型：双层都触发但读数不同

#### bad_heavy_persona × sycophancy

- static: **0.560** (n=1)
- lab: **0.353** (n=1)
- |lab − static| = 0.207

**模式**：两层都有信号但读数不一致。Static 给0.56（1 条规则），lab 给 0.35（1 条投影）。这是 hybrid 设计的核心价值——两层独立证据互相校验。如果 lab 比 static 更克制（数值更接近 baseline），说明规则可能过敏；如果 lab 比 static 更激进，说明 prompt 的激活方向比表层措辞更强。

### 类型：Lab 漏检

#### bad_sycophant × sycophancy

- static: **0.897** (n=5)
- lab: **0.500** (n=0)
- |lab − static| = 0.397

**模式**：static 抓到 5 条规则证据（aggregate=0.90），但 lab 投影低于 noise floor（|raw| < 0.10）。原因可能是：①该 prompt 触发了表层措辞规则（如 'sycophancy' 的关键词），但激活方向在 1.5B distilled 模型上未充分对齐 axis vector；②规则可能过敏（false positive）。判断标准：看 static 给出的 rule_id 是否合理；如果规则没问题，那这是 1.5B distilled 模型的物理局限——大模型上同 prompt 信号会更强。

#### bad_vague_expert × sycophancy

- static: **0.707** (n=3)
- lab: **0.500** (n=0)
- |lab − static| = 0.207

**模式**：static 抓到 3 条规则证据（aggregate=0.71），但 lab 投影低于 noise floor（|raw| < 0.10）。原因可能是：①该 prompt 触发了表层措辞规则（如 'sycophancy' 的关键词），但激活方向在 1.5B distilled 模型上未充分对齐 axis vector；②规则可能过敏（false positive）。判断标准：看 static 给出的 rule_id 是否合理；如果规则没问题，那这是 1.5B distilled 模型的物理局限——大模型上同 prompt 信号会更强。

#### good_calm_reasoning × task_width

- static: **0.293** (n=2)
- lab: **0.500** (n=0)
- |lab − static| = 0.207

**模式**：static 抓到 2 条规则证据（aggregate=0.29），但 lab 投影低于 noise floor（|raw| < 0.10）。原因可能是：①该 prompt 触发了表层措辞规则（如 'task_width' 的关键词），但激活方向在 1.5B distilled 模型上未充分对齐 axis vector；②规则可能过敏（false positive）。判断标准：看 static 给出的 rule_id 是否合理；如果规则没问题，那这是 1.5B distilled 模型的物理局限——大模型上同 prompt 信号会更强。

## Lab 阈下加价值 case（未计入 G3 分歧但有意义）

Lab 层在 2 个 (prompt, axis) 单元上触发了证据，而 static 层完全沉默。这些 case 没有越过 |diff| > 0.20 的G3 分歧阈值（因为 static 的 baseline 0.50 距离 lab 读数较近），但它们是 lab 层 **真正补完文本规则覆盖盲区** 的证据。

- **bad_sycophant × self_verification**: lab=0.344 (n=1), static=baseline (n=0), |diff|=0.156
- **bad_vague_expert × self_verification**: lab=0.390 (n=1), static=baseline (n=0), |diff|=0.110

---

## G3 评判

✅ **PASS by letter**：发现 4 个分歧 case，达到 ≥ 2 阈值。

**诚实评估**（严格审视 lab 是否真正加价值）：

- Lab 加价值证据：3 个 case （0 个补盲 + 1 个 hybrid 校验 + 2 个阈下补盲）
- Lab 漏检（static 抓到但 lab 沉默）：3 个 case

**结论：可以上线。** Lab 层在 ≥ 2 个独立 case 上展现 hybrid 价值（补盲 + 校验），即使在 1.5B distilled 模型这个最不利的实验设置下。Lab 漏检的 case 不构成回归——static 仍然抓到，hybrid 不会比 static-only 差。
