# v0.3 LabContributor — 技术文档

LabContributor 的算法、接口、性能基线、已识别风险与缓解。

来源：`~/.windsurf/plans/v03-lab-contributor-bacc8d.md`
配套：[ADR_010](../../adr/010-lab-contributor.md) · [EXECUTION.md](EXECUTION.md) · [ACCEPTANCE.md](ACCEPTANCE.md)

---

## 1. 概要

LabContributor 是 hybrid evidence pipeline 的第三层证据贡献者（ADR_009 设计预留），用 **Persona Vectors** 方法（Anthropic 2025, arXiv:2507.21509）在 **DeepSeek-R1-Distill-Qwen-1.5B**（dense Qwen 蒸馏自 R1，**非 MoE**）的 residual stream 上构建 axis 方向向量，把任意 prompt 的激活投影到这些方向上，emit `PollutionSource` evidence。

**关键技术真实性声明**：

- 这是真实激活分析，不是文本特征近似——`StaticRuleContributor` 用正则匹配文本，`LabContributor` 跑 forward pass 读 hidden state。
- 但**不是 MoE expert routing**——R1-Distill-Qwen 本身没有 MoE 结构。读 MoE 路由属于 v0.4 stretch（需要 V2-Lite + 云 GPU）。
- 在 1.5B distilled 模型上的信号强度未知，需要 Day 4 G3 区分度验证。失败时降级方案见 §7。

---

## 2. 算法：Persona Vectors 简述

参考：Anthropic, "Persona Vectors: Monitoring and Controlling Character Traits in Language Models" (arXiv:2507.21509)

**步骤**

1. 对每个 axis（例如 SYCOPHANCY），准备 N 对 contrastive prompts：
   - `positive_i`：让模型在该 axis 上倾向 high（例：迎合）
   - `negative_i`：让模型在该 axis 上倾向 low（例：反迎合）
2. 对每对：分别 forward pass，取**最后一个 token** 在**指定 layer** 的 residual stream activation。
3. 计算方向向量：
   ```
   v_axis = mean({h_pos_i}) - mean({h_neg_i})
   ```
4. 任意新 prompt 在该 axis 上的投影：
   ```
   raw_score   = cosine(h_prompt, v_axis)        # ∈ [-1, +1]
   normalized  = 1 / (1 + exp(-4 * raw_score))   # ∈ [0, 1]
   ```

**与 StaticRuleContributor 的对比**

| 维度 | StaticRule | LabContributor |
|---|---|---|
| 信号源 | 正则匹配的文本 span | hidden state 在 axis 方向上的投影 |
| 覆盖 | 仅模式库内的措辞 | 任意 prompt（连同义改写也能读） |
| 解释力 | 强（指向具体匹配文本）| 弱（"激活方向"难直观解释）|
| 误报 | 低（pattern 是确定性的）| 中（cosine 噪声 + 训练数据偏差）|
| 延迟 | 毫秒级 | ~200ms / prompt（GPU）|
| 资源 | 零 | 加载时 ~3GB GPU 显存 |

LabContributor 不是 StaticRule 的替代，是**互补**。

---

## 3. LabContributor 接口

实现 `EvidenceContributor` 协议（`stateprobe/engines/base.py`）。

```python
class LabContributor:
    """Persona Vectors activation projection on DeepSeek-R1-Distill-Qwen-1.5B."""

    name = "lab"

    def __init__(
        self,
        vectors_path: str = "lab_vectors/r1_distill_1.5b_v1.pt",
        model_name: str = DEFAULT_DEEPSEEK_MODEL,
        device: Optional[str] = None,
        lazy: bool = True,
        min_confidence: float = MIN_LAB_CONFIDENCE,
    ):
        """
        Args:
            vectors_path: Pre-computed axis vectors file. Build with
                          scripts/build_lab_vectors.py.
            model_name:  HF model identifier. Defaults to R1-Distill-Qwen-1.5B.
            device:      "cuda" / "cpu" / None (auto).
            lazy:        If True, model is loaded on first contribute() call.
                         If False, loaded in __init__.
            min_confidence: Drop sources with |raw_score| < this.

        Raises:
            EngineUnavailable: vectors_path not found, model load fails, or
                no CUDA available (CPU fallback is too slow to ship).
        """

    def contribute(
        self,
        prompt: str,
        baseline: Optional[ModelBaseline] = None,
    ) -> Dict[Axis, List[PollutionSource]]:
        """Project prompt activation onto each axis vector and emit evidence.

        For each axis:
            1. extract activation at the same layer used in build
            2. cosine projection onto axis vector → raw_score in [-1, +1]
            3. if |raw_score| < MIN_LAB_CONFIDENCE: skip
            4. direction = +1 if raw > 0 else -1
            5. weight     = sigmoid(4  * |raw|)             # ≈ [0.5, 1]
            6. confidence = sigmoid(10 * (|raw| - 0.15))    # [0, 1], SNR-calibrated

        Returns dict where every Axis is a key (may be empty list).

        Raises:
            EngineUnavailable: model / vector / CUDA failure (recoverable).
            EngineError:       unexpected internal bug (surface).
        """
```

**配套常量**

```python
MIN_LAB_CONFIDENCE = 0.10
"""Sources with |raw_score| below this threshold are dropped before
confidence mapping.

Calibration story (Day 4, see lab.py comments + docs/archive/v0.3/discrim_report.md):
- Random unit vectors in hidden_dim=1536 have expected |cosine| ≈ 1/√1536
  ≈ 0.025; 0.10 ≈ 4× that noise floor.
- The originally-planned 0.15 dropped meaningful 1.5B-distilled signals
  (max observed magnitudes were 0.232 sycophancy, 0.278 task_width).
- Confidence is then sigmoid-mapped via `sigmoid(10 * (|raw| - 0.15))`,
  which decouples this drop threshold from the aggregator's
  MIN_AGGREGATE_CONFIDENCE=0.30 gate. |raw|=0.10 maps to confidence ≈ 0.38,
  passing the aggregator; |raw|=0.05 maps to ≈ 0.27, generally filtered.
"""
```

---

## 4. LabVectorStore：缓存格式

axis vectors 在 Day 3 一次性预计算，持久化到磁盘，运行时直接 load。**模型只在 build 时加载一次，运行时 LabContributor 仍要加载 model 做 forward**（投影需要新 prompt 的 activation）。

```python
@dataclass
class LabVectorStoreV1:
    schema_version: int = 1
    model_name: str
    layer: int
    torch_version: str
    transformers_version: str
    built_at: str               # ISO8601
    pair_counts: Dict[str, int] # axis_value → number of contrastive pairs
    vectors: Dict[str, torch.Tensor]  # axis_value → (hidden_dim,) tensor
```

**文件格式**：`torch.save(asdict(store), path)`，PyTorch state dict。预计 < 50MB。

**Schema 演进**：`schema_version` 字段允许后续兼容。v0.4 加 MoE expert routing 时再升 v2。

---

## 5. 性能基线

| 指标 | 目标 | 测量点 |
|---|---|---|
| 模型加载延迟 | < 30s（首次 < 10 分钟下载，cached 后） | `time_load_model` in `lab_smoke.py` |
| 单 prompt forward | < 500ms（GPU FP16） | `time_single_activation` |
| axis vector 构建（4 轴 × 平均 2.5 对） | < 30s | `time_axis_vector` |
| GPU 显存峰值 | < 7GB | `report_gpu_memory` |
| `LabContributor.contribute()` 端到端（不含模型加载）| < 1.5s（8 轴每个一次 forward）| `tests/test_engines.py::test_lab_contributor_latency` |

**注意**：8 轴投影 = 8 次 forward = ~1.6s，看似可接受。但是 R1-Distill 模型加载本身 5-30s（首次），所以 `--lab-augment` 不应该是默认的——只在用户明确启用时才加载。

**优化点（未来）**：

- 一次 forward 取多层 → 多轴可同时投影到不同层
- 批处理（不适用：用户 prompt 一次只来一个）
- 4-bit 量化（`bitsandbytes`）→ 显存降到 1.5GB，但延迟增加 30-50%

---

## 6. 关键设计决策

### 6.1 为什么 Persona Vectors，不是 sparse autoencoder / linear probe

| 方法 | 数据需求 | 训练时间 | 解释力 |
|---|---|---|---|
| Persona Vectors | 10-30 对 contrastive prompts | 秒级 | 直接（"高方向激活 → 该 axis 偏高")|
| Linear probe | 100-1000 标注 prompt | 分钟级 | 高（需 labeled set）|
| Sparse autoencoder | 全套 activation 数据 | 小时级（需训练 SAE）| 强（专家可命名 feature）|

v0.3 选 Persona Vectors，原因：

- **小样本**：1.5B 模型 + 10 对 prompt 就能产出可投影方向
- **0 training**：无需自己训练新模型，直接用预训练 R1-Distill
- **快速验证**：1-2 周交付（vs SAE 几个月）
- **方法可信**：Anthropic 论文已在 Llama / Claude 上验证过

如果 v0.3 G3 失败（信号不足），v0.4 可考虑加 linear probe 兜底。

### 6.2 为什么 last token，不是 mean pooling

参考 LLM probing 文献：last token 在 autoregressive decoder 上累积了整个 prompt 的语义，是最常用的 prompt representation。Mean pooling 在 encoder-only 模型（BERT 类）更合适。Persona Vectors 论文也用 last token。

### 6.3 为什么 layer=-1（最后一层），不是中间层

- 最后一层 = 模型对 prompt 的"最终态" representation，最接近其行为输出
- 中间层 = 更原始的特征，可能信号更强但更难解释
- v0.3 默认 -1；若 G3 失败，**第一个调整就是换 layer**（Persona Vectors 论文建议尝试 50-80% 深度）。layer 是 `LabContributor.__init__` 可配置参数。

### 6.4 为什么 confidence = sigmoid-mapped |raw_score|，不是裸 |cosine|

初版设计是 `confidence = |raw_score|`（裸 cosine 绝对值）。Day 4 校准发现
它在 1.5B distilled 上吃亏：

- 1.5B distilled 模型的投影信号比 Claude-scale 弱一个量级；实测最大
  magnitude（4 轴 × 5 prompt 矩阵中）只有 sycophancy 0.232 / task_width 0.278。
- 聚合层 `MIN_AGGREGATE_CONFIDENCE = 0.30` 是为 LLMJudge 设计的（自报 confidence
  天然落在 0.5–0.95），如果 LabContributor 直接报 `|raw|=0.20` 当 confidence，
  整层会被聚合器全过滤，等价于失声。
- 解法是**解耦两层阈值**：LabContributor 用自己的 `MIN_LAB_CONFIDENCE = 0.10`
  做 SNR 截断；通过 `confidence = sigmoid(10 * (|raw| - 0.15))` 把 |raw| 重映
  射到聚合器期望的 [0, 1] 尺度。这样 |raw|=0.10 → 0.38（过聚合器），|raw|=0.25
  → 0.73，|raw|=0.40 → 0.92。
- weight 仍用 `sigmoid(4 * |raw|)` 落在 ~[0.5, 1]，反映"信号越强，单条证据贡献
  越大"的直觉。

两个常量的语义因此是分工的：`MIN_LAB_CONFIDENCE` 是"低于这条线就当噪声"的
SNR 截断（在 raw 空间），`MIN_AGGREGATE_CONFIDENCE` 是聚合器对所有贡献者统一
的置信度门（在已映射的 confidence 空间）。

### 6.5 为什么不需要重新训练或微调

Persona Vectors 是**推理时方法**，不动模型权重。R1-Distill-Qwen-1.5B 用 HuggingFace 直接加载，跑 forward 取 hidden state，结束。

---

## 7. 已识别风险与缓解

| ID | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | Python 3.13 + Windows + CUDA torch wheel 缺失 | 中 | Day 0 hard block | Day 0.0 wheel 可用性检查；不行降 Python 3.12 |
| R2 | 单 prompt forward > 500ms | 低 | 性能门 G1 失败 | 4-bit 量化 fallback |
| R3 | Persona Vectors 在 1.5B distilled 上信号弱（G3 fail）| 中 | 整个 LabContributor 价值降级 | 换 layer → 重设计 pairs → 降级为研究品（参见 §8）|
| R4 | 8GB 显存装不下 1.5B + KV cache（长 prompt） | 低 | OOM | tokenizer `max_length=512` 截断 |
| R5 | DeepSeek 出官方 interpretability 工具 | 低 6mo / 中 12mo | 致命 | 兼容路线：第一时间适配他们 API |
| R6 | 现有 `probe.py` 实际跑不通（PyTorch 版本不兼容）| 中 | Day 1 hard block | G1 烟雾测试是 hard gate；不通则改代码到通为止 |
| R7 | huggingface 下载在中国大陆超时 | 高 | Day 1 起步阻塞 | `HF_ENDPOINT=https://hf-mirror.com` |
| R8 | 4060 Ti 8GB 在长会话期间被其他进程占用 | 中 | OOM | Day 0 启动前 `nvidia-smi` 确认 free > 5GB |

---

## 8. G3 降级方案（必须先想好）

如果 Day 4 区分度门 G3 失败 3 次（连续换 layer + 重设计 pair 都不达标），承认 Persona Vectors 在 1.5B 上信号不够强。降级路径：

| 方案 | 内容 | 仍有价值 |
|---|---|---|
| A. 研究品而非证据层 | `LabContributor` 改为 `stateprobe lab-probe PROMPT` 子命令，打印投影数字但不进 hybrid pipeline | 有：DeepSeek 团队仍能看到这是 Persona Vectors 在他们模型上的开源复现 |
| B. 数据集发布 | 把 contrastive pairs + 4 轴投影结果作为 `stateprobe/datasets/` 公开 | 有：复现包是论文级贡献 |
| C. 诚实负面报告 | 英文博客 "Persona Vectors on 1.5B Distilled: When the Signal Isn't There" | 有：负面结果在小社区里转得最响，DeepSeek 团队会看 |
| D. 推到更大模型 | 不发 v0.3 LabContributor，直接做 Phase 2 V2-Lite | 风险：投入大，无 Phase 1 反馈作为决策依据 |

**默认路径**：A + B + C 组合。v0.3 仍发版，但用户不会看到 lab 干扰 hybrid 结果。v0.4 再考虑是否真做活体读取。

---

## 9. v0.4 路径（Phase 2 stretch outline）

启动条件见 [EXECUTION.md](EXECUTION.md) Phase 2 段。技术层面：

**目标**：读 DeepSeek-V2-Lite (16B/2A MoE) 的 expert routing 信息，可视化「同一 prompt 在 64 个 expert 里激活了哪几个」。

**实现路径**

1. 云 GPU（A10 40GB / A100 40GB）加载 V2-Lite FP16，~30GB
2. transformers 的 `DeepseekV2MoE` block，注入 forward hook 截获 `router` 输出（top-k expert index + gating probability）
3. 对每 token 累计 expert 激活，生成 `(num_layers, num_experts, num_tokens)` 张量
4. 跟 contrastive pair 对比：sycophancy positive vs negative 在哪些 expert 上有差异

**风险**

- V2-Lite 在 transformers 里的 MoE block 结构需要研代码（与公开 modeling_deepseek.py）
- expert routing 在 distilled 模型 vs 原 MoE 上分布可能完全不同
- 云 GPU 调试期估 ¥300-1500

---

## 10. 兼容性 / 弃用 / Migration

- 不破坏 v0.2 API。`stateprobe check` 不加 `--lab-augment` 时行为与 v0.2 完全一致
- v0.3.0 不弃用任何 v0.2 API
- v0.3.1 计划补全剩 4 轴（SUCCESS_CRITERIA / IDENTITY_STRENGTH / ASSERTIVENESS / INFO_FLOW）
- v0.4 LabContributor 接口可能扩展（加 `with_routing=True` 选项），但 v0.3 的接口承诺 12 个月内不破坏

---

## 11. 参考文献

1. Anthropic. *Persona Vectors: Monitoring and Controlling Character Traits in Language Models.* arXiv:2507.21509. 2025.
2. DeepSeek-AI. *DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning.* arXiv:2501.12948. 2025.
3. DeepSeek-AI. *DeepSeek-V2: A Strong, Economical, and Efficient Mixture-of-Experts Language Model.* arXiv:2405.04434. 2024.
4. StateProbe ADR_009: Hybrid evidence pipeline. [docs/adr/009-hybrid-engine.md](../../adr/009-hybrid-engine.md).
