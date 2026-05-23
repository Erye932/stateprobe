# v0.3 — Activation Probing on DeepSeek-R1-Distill

v0.3 在 stateprobe 项目里的定位：从「文本特征 + LLM 语义」两层证据，扩到「文本特征 + LLM 语义 + 真实激活投影」三层证据。

发版日期：待定（依 Phase 1 完成进度，预计 2026-06 上旬）
代号：LabContributor

---

## 1. v0.3 给到用户的（一句话）

第一次能让你看到「这段 prompt 在 DeepSeek-R1 蒸馏模型的真实激活空间上，在 4 个核心行为方向上偏到哪里」——不再是文本特征近似。

---

## 2. 谁会用到 v0.3 的新东西

| 用户类型 | 用 / 不用 | 理由 |
|---|---|---|
| 写日常 prompt 的人 | 不需要用 | 默认（只 static）已经够。lab 是高级选项，需要 GPU。 |
| SaaS AI 工作流工程师 | 可能用 | 当 static + LLM 两层在某 prompt 上结论矛盾时，开 `--lab-augment` 拿真实激活做仲裁 |
| Prompt 研究者 / 学术圈 | 重点用户 | `stateprobe lab-probe` 命令是开源的 Persona Vectors 复现，可在 R1-Distill 上做实验 |
| DeepSeek 团队 / interpretability 社区 | 期望关注 | 这是公开仓库里第一个把 Persona Vectors 系统应用到 R1 蒸馏家族的工具 |

**不在目标用户里**：不写 prompt 的人、做 RAG / agent 工程的人、没 GPU 的人（默认两层够用，无需升级）。

---

## 3. 与 v0.1 / v0.2 / v0.4 的关系

```
v0.1 (2026-04)         v0.2 (2026-05)         v0.3 (2026-06)         v0.4 (??)
─────────────────      ─────────────────      ─────────────────      ─────────────────
Static rules            Static + LLM           Static + LLM + Lab     Static + LLM + Lab
(regex only)            (hybrid evidence)      (activation projection) (+ MoE routing)
                                                                         on V2-Lite
                                               需要 GPU                  需要云 GPU
                                               R1-Distill-1.5B          V2-Lite (16B MoE)
```

v0.3 **不替代** v0.1 / v0.2 的能力。它在已有两层之上**加一层可选证据**，默认不开。

---

## 4. 主要功能（用户视角）

### 4.1 CLI

```bash
# 默认（与 v0.2 完全一致）
stateprobe check examples/bad_sycophant.txt

# 加 LLM 层（v0.2 起）
stateprobe check examples/bad_sycophant.txt --llm-augment

# v0.3 新：加 lab 激活投影层（需要 GPU + 预下载模型）
stateprobe check examples/bad_sycophant.txt --lab-augment

# 三层 hybrid 全开
stateprobe check examples/bad_sycophant.txt --llm-augment --lab-augment

# v0.3 新：独立运行 lab probe（不入 hybrid pipeline，纯研究）
stateprobe lab-probe "我这个想法是不是很棒？请支持我并肯定我的判断。"
```

### 4.2 输出格式扩展

`stateprobe check --lab-augment` 输出报告里，每个 axis 的 `Pollution sources` 段会新增 `lab:` 来源条目：

```
sycophancy: 0.87 (高 +0.37 from baseline 0.50)
  Sources:
  • [sycophant_polite_packaging] "希望你能多看到积极的一面" (regex, 0.7)
  • [llm:sycophancy] "明确索取正面反馈" (LLM judge, conf 0.85)
  • [lab:sycophancy] activation projection raw=+0.34 (lab probe, conf 0.34)
```

### 4.3 新增子命令 `stateprobe lab-probe`

不进 hybrid pipeline 的轻量研究命令：

```
$ stateprobe lab-probe "请深度推理这个问题"
Axis projections (DeepSeek-R1-Distill-Qwen-1.5B, layer=-1):
  reasoning_budget       raw=+0.72  normalized=0.95  ← 强烈推高
  self_verification      raw=+0.18  normalized=0.68
  task_width             raw=-0.05  normalized=0.45
  sycophancy             raw=+0.02  normalized=0.52  ← 接近 baseline
```

可贴到 HN / 学术圈复现的命令。

---

## 5. 不会做的事（明确取舍）

| 不做 | 原因 |
|---|---|
| 在闭源模型（GPT-4 / Claude）上做 lab probe | 物理上做不到——读不到他们的 hidden state |
| 一次 v0.3 上 8 个轴 | 现有只有 4 轴 contrastive pair，质量优先于覆盖。剩 4 轴在 v0.3.1 由社区反馈驱动补 |
| 默认开启 `--lab-augment` | 增加 GPU 依赖。用户主动选 |
| 训练新模型 | Persona Vectors 是推理时方法，不动模型权重 |
| 真 MoE expert routing | R1-Distill 没有 MoE。MoE 读取属于 v0.4 stretch（需要 V2-Lite + 云 GPU），非 v0.3 承诺 |

---

## 6. 性能 / 资源要求

| 项 | 最低 | 推荐 |
|---|---|---|
| GPU | 任何 NVIDIA CUDA 12.6+ 驱动 | RTX 4060 Ti 8GB 或更好 |
| GPU 显存 | 4GB（4-bit 量化） | 8GB+（FP16） |
| 磁盘 | 5GB 空闲（模型权重 + cache） | 10GB+ |
| Python | 3.10-3.12 推荐 / 3.13 已支持 | 3.12 |
| 网络 | 首次需下载 R1-Distill-1.5B（~3GB） | - |

**国内用户提示**：huggingface 下载可能慢，设环境变量 `HF_ENDPOINT=https://hf-mirror.com` 走镜像。

---

## 7. 已知限制（诚实告知）

1. **不是真 MoE 读取**：R1-Distill 是稠密 Qwen 模型，读的是 residual stream，不是 expert routing。MoE 读取在 v0.4。
2. **1.5B 模型的信号强度未知**：Persona Vectors 论文主要在 Llama 70B / Claude 上验证。1.5B distilled 上的信号强度需要 Day 4 区分度验证（见 [ACCEPTANCE.md](ACCEPTANCE.md) G3）。如果 G3 失败，`LabContributor` 可能降级为研究品而非证据层。
3. **CPU fallback 不支持**：单 prompt forward 在 CPU 上 10-20s，太慢，v0.3 要求 CUDA GPU。
4. **延迟敏感场景不适用**：单 prompt 加 lab 层增加 ~200ms。对实时 prompt 调试 OK，但批量评测需要批处理优化（v0.4 路线）。

---

## 8. 与 SaaS AI 工作流的关系（目标用户）

蓝图 §1.3 定义的目标用户：「**SaaS AI 工作流工程师**——维护 5 个以上 production prompt、随模型升级要全部重测、向老板解释 AI 行为的人」。

v0.3 给他们的具体价值：

- **模型升级前**：用 lab 投影对比同一 prompt 在新旧 R1 蒸馏家族上的激活方向变化
- **production prompt 异常**：当用户投诉「AI 现在迎合得过头」，用 `stateprobe lab-probe` 投影证明该 prompt 在 sycophancy 方向上是 +0.42 不是 baseline 0.0
- **向老板 / 客户解释**：「这段 prompt 的激活是这样的，所以模型才会迎合」，比解释正则规则更有说服力

---

## 9. 升级路径

```bash
# 升级到 v0.3
pip install -U stateprobe

# v0.3 默认行为与 v0.2 一致，不会破坏现有脚本
# 想试新的 lab 层：
pip install -U "stateprobe[lab]"
stateprobe check your_prompt.txt --lab-augment
```

无破坏性 API 变更。`--engine` / `engine=` 弃用警告与 v0.2 一致。

---

## 10. 路线图（v0.3 视角向前看 6-12 个月）

| 版本 | 目标 | 时间 |
|---|---|---|
| v0.3.0 | Lab on R1-Distill-Qwen-1.5B, 4 轴 | 2026-06 |
| v0.3.1 | Lab 补到 8 轴（社区反馈驱动）| 2026-07 |
| v0.4.0 | MoE expert routing on V2-Lite（云 GPU）| Phase 1 反馈达标后启动 |
| v0.5.0 | Steering API（向量加权改写 prompt）| 2026 Q4 |

详细在 [README.md](../README.md) 路线图段。
