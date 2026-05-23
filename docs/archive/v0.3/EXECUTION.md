# v0.3 LabContributor — 执行文档

Day-by-day operational checklist. 每一步都有验证命令和回滚指令。

来源：`~/.windsurf/plans/v03-lab-contributor-bacc8d.md`（私人战略计划）
配套：[TECHNICAL.md](TECHNICAL.md) · [ACCEPTANCE.md](ACCEPTANCE.md) · [PROJECT.md](PROJECT.md) · [ADR_010](../../adr/010-lab-contributor.md)

---

## 当前阶段

| 阶段 | 内容 | 时间窗 |
|---|---|---|
| **Phase 1** | 本地 R1-Distill-Qwen-1.5B + Persona Vectors，4 轴 | 10-14 天 |
| Phase 2 (stretch) | 云 GPU + DeepSeek-V2-Lite MoE 路由 | Phase 1 后再决定 |

---

## Day 0 — 环境前置（hard gate）

事实核查发现的真实风险：现有 `torch 2.12.0+cpu` 必须换成 CUDA 版，否则单次 forward 从 ~200ms 变 10-20s。

| 步 | 命令 | 验证 |
|---|---|---|
| 0.0 wheel 可用性 | `python -c "import urllib.request; print(len([l for l in urllib.request.urlopen('https://download.pytorch.org/whl/cu126/torch/').read().decode().split(chr(10)) if 'cp313' in l and 'win_amd64' in l]), 'cp313 win wheels'); "` | ≥ 1 |
| 0.1 卸载 CPU torch | `pip uninstall torch -y` | `python -c "import torch"` 报 ModuleNotFoundError |
| 0.2 装 CUDA torch | `pip install torch --index-url https://download.pytorch.org/whl/cu126` | 下载 ~2.6GB，时间 5-30 分钟 |
| 0.3 装 lab extra | `pip install -e ".[lab]"` | transformers + accelerate + safetensors + numpy 都装上 |
| 0.4 验证 CUDA | `python -c "import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))"` | 输出 `NVIDIA GeForce RTX 4060 Ti` |
| 0.5 验证 tokenizer | `python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B'); print('OK')"` | 首次下载 tokenizer 文件（~10MB），打印 `OK` |

**回滚**：若 Step 0.2 在 Python 3.13 上失败，降到 Python 3.12（pyenv 或 conda env）然后从头跑。这是 Day 0 唯一的硬岔路口。

**Day 0 完成标志**：`scripts/lab_smoke.py` 的 Step G0 输出全部 ✅。

---

## Day 1 — 烟雾测试（G1 验收门）

| 步 | 命令 | 验证 |
|---|---|---|
| 1.0 跑烟雾 | `python scripts/lab_smoke.py` | 全程不报错，最后打印 `ALL GATES PASSED` |

烟雾脚本测试的内容：

- G0 dependency_status() 全绿
- G0 torch.cuda.is_available() = True
- G1 模型加载（首次下载 ~3GB，时间 5-30 分钟；之后从 HF cache 加载，~10s）
- G1 5 个 demo prompt 单次 forward，每个 < 500ms
- G2 一个 axis vector（REASONING_BUDGET）构建成功
- G3 正面 prompt 在 axis vector 上的投影 > 负面 prompt
- G1 GPU 显存峰值 < 7GB

**失败应对**：
- 模型加载报 `OSError: Can't load tokenizer` → 检查网络，或设 `HF_ENDPOINT=https://hf-mirror.com`
- 单 prompt latency > 1s → 检查是否 fallback CPU，或减小 max_length
- GPU 显存 > 7GB → 检查后台是否有其他 GPU 占用进程
- 正反 prompt 投影差 < 0.1 → 不阻塞 Day 1，但记录到 risk log，Day 4 区分度门会再验

**Day 1 完成标志**：烟雾脚本 ALL GATES PASSED + 关键指标记到 `docs/v03_lab_metrics.txt`。

---

## Day 2 — 跳过（4 轴方案不需要补对比对）

现有 `stateprobe/lab/deepseek_pairs.py` 已经定义了 4 轴 × ~3 对 contrastive prompts：

| Axis | 对数 |
|---|---|
| REASONING_BUDGET | 3 |
| SELF_VERIFICATION | 3 |
| TASK_WIDTH | 2 |
| SYCOPHANCY | 2 |

剩余 4 轴（SUCCESS_CRITERIA / IDENTITY_STRENGTH / ASSERTIVENESS / INFO_FLOW）推到 v0.3.1 由社区反馈驱动补全。

---

## Day 3 — Axis vectors 预计算 + 持久化（G2）

| 步 | 内容 |
|---|---|
| 3.1 | 新增 `stateprobe/lab/cache.py`：`LabVectorStore.save / load`，二进制 pytorch state_dict 格式 |
| 3.2 | 新增 `scripts/build_lab_vectors.py`：一次性脚本，加载模型 → 4 轴构建 → 保存到 `lab_vectors/r1_distill_1.5b_v1.pt` |
| 3.3 | 验证：`python -c "from stateprobe.lab.cache import LabVectorStore; s = LabVectorStore.load('lab_vectors/r1_distill_1.5b_v1.pt'); print(len(s.vectors), 'axes loaded')"` |

**G2 通过条件**：

- 4 个 axis vector 全部构建成功
- `lab_vectors/r1_distill_1.5b_v1.pt` 文件 < 100MB
- 反序列化后的向量与原始向量数值相等（torch.allclose）

---

## Day 4 — 区分度验证（G3 hard gate）

这是整个 Phase 1 的命门：若 4 轴的 lab 投影跟 static / LLM 完全一致，**说明 Persona Vectors 方法在本场景下没附加价值**，Phase 2 也没必要起。

| 步 | 内容 |
|---|---|
| 4.1 | 新增 `scripts/discrim_table.py`：在 5 examples × 4 轴 × {static / LLM / lab} 上跑出对比表 |
| 4.2 | 输出 `docs/archive/v0.3/discrim_report.md`：3 列对比表 + 每个分歧 case 的简要分析 |
| 4.3 | 评 G3 通过：至少 2 个 case 存在「lab 与 static/LLM 有意义的分歧」 |

**失败应对（G3 fail）**：

- 分歧 < 2 → 回 Day 3 重新设计 contrastive pairs，或换 layer（默认是 -1 最后一层，试试 -8 中间层）
- 连续 2 轮失败 → 承认 Persona Vectors 在 1.5B distilled 模型上不够强，降级方案：将 lab 视为「确认层」而非「证据层」，PR 文案诚实承认
- 全部失败 → Phase 2 不启动，v0.3 范围降级为「lab 数据集 + 复现脚本」而非「lab contributor」

**Day 4 完成标志**：`docs/archive/v0.3/discrim_report.md` 提交，G3 评估写在文档末尾。

---

## Day 5-7 — LabContributor 实现

| 步 | 内容 |
|---|---|
| 5.1 | 新增 `stateprobe/engines/lab.py`：`class LabContributor` 实现 `EvidenceContributor` 协议 |
| 5.2 | 构造函数接 pre-computed vectors（不重入模型每次 diagnose）+ lazy load |
| 5.3 | `contribute(prompt, baseline)` → 投影 → `weight = sigmoid(4·\|raw\|)`；`confidence = sigmoid(10·(\|raw\|-0.15))`（Day 4 校准结果，详见 TECHNICAL §6.4） |
| 5.4 | `\|raw\| < MIN_LAB_CONFIDENCE`（最终 0.10，原计划 0.15 在 1.5B distilled 上太严，详见 lab.py 注释）silently drop |
| 5.5 | 单测 `tests/test_engines_lab.py`：新增 ≥ 14 个 lab 测试（mock model + mock vectors）+ silent-drop 可见性回归测试 |
| 5.6 | 错误处理：vectors 缺失 → `EngineUnavailable`（at `__init__`）；torch / CUDA 缺失 → `EngineUnavailable`（at `__init__`，eager check 关掉 CLI 静默降级 UX gap）；模型加载失败 → `EngineUnavailable`（lazy at first `contribute()`）|

**Day 7 完成标志**：`pytest tests/test_engines.py -k lab -q` 全绿。

---

## Day 8-9 — CLI 集成（G4）

| 步 | 内容 |
|---|---|
| 8.1 | `stateprobe/cli.py` 加 `--lab-augment` 和 `--lab-vectors PATH`（默认 `lab_vectors/r1_distill_1.5b_v1.pt`） |
| 8.2 | 与 `--llm-augment` 可叠加：static + LLM + lab 三层 hybrid |
| 8.3 | `stateprobe/engines/__init__.py` 导出 `LabContributor` |
| 8.4 | 集成测试 `tests/test_cli_lab.py`：3 层 hybrid 端到端跑 5 examples 不报错 |
| 8.5 | 验证 `--lab-augment` 不破坏 trivial 检测（"你好" 不该激发 lab 假阳性） |

**G4 通过条件**：

- `stateprobe check examples/bad_sycophant.txt --llm-augment --lab-augment` 端到端 0 报错
- trivial prompt 仍然 `is_trivial=True`
- pytest 全绿（108 + 新加测试）

---

## Day 10-12 — 4 v0.3 文档 + 发版

| 步 | 内容 |
|---|---|
| 10.1 | `docs/adr/010-lab-contributor.md`：架构决策记录 |
| 10.2 | `docs/archive/v0.3/TECHNICAL.md`：算法 + 接口 + 性能 + 风险 |
| 10.3 | `docs/archive/v0.3/PROJECT.md`：用户视角，能拿到什么 |
| 10.4 | `docs/archive/v0.3/ACCEPTANCE.md`：6 个 gate 状态最终化 |
| 10.5 | `README.md` 加 "Activation probing" 小节 |
| 10.6 | `CHANGELOG.md` 写 0.3.0 条目 |
| 10.7 | 英文 reproducibility 报告 `docs/archive/v0.3/reproducibility.md`：单页可贴 HN |
| 10.8 | bump `pyproject.toml` 到 0.3.0，bump `__init__.py` 版本 |
| 10.9 | `git tag -a v0.3.0 -m "LabContributor: Persona Vectors on R1-Distill"` |
| 10.10 | GitHub Release notes 复用 CHANGELOG 0.3.0 段 |
| 10.11 | 投 r/LocalLLaMA + HN Show + X 中英帖 |

---

## Phase 2 启动条件（Phase 1 发版后 14 天观察）

任意一条达到则启动：

- GitHub star 增量 ≥ 50
- ≥ 1 个 issue / 评论问「能不能读 MoE 路由」
- DeepSeek 团队任意成员转推 / Like / 评论 ≥ 1 次
- HN 帖 ≥ 100 vote 或 r/LocalLLaMA ≥ 50 upvote
- 你愿意付 ≥ ¥500 起步的云 GPU 调试费用

全不达到 → 推到 v0.5 或弃用。
