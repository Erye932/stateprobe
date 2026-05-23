# v0.3 LabContributor — 验收文档

发版前必须全过的 7 个 gate。每个 gate 有：通过条件、验证命令、失败应对。

来源：`~/.windsurf/plans/v03-lab-contributor-bacc8d.md` §6
配套：[EXECUTION.md](EXECUTION.md) · [TECHNICAL.md](TECHNICAL.md) · [PROJECT.md](PROJECT.md)

---

## 验收门总览

| Gate | 阶段 | 性质 | 状态 |
|---|---|---|---|
| **G0** 环境就绪 | Day 0 | hard gate | ⬜ |
| **G1** 烟雾测试通过 | Day 1 | hard gate | ⬜ |
| **G2** 向量预计算 + 持久化 | Day 3 | hard gate | ⬜ |
| **G3** 区分度验证 | Day 4 | hard gate（决定 Phase 2 是否启动）| ⬜ |
| **G4** 三层 hybrid 集成 | Day 8-9 | hard gate | ⬜ |
| **G5** 测试套件全绿 | Day 9 | hard gate | ⬜ |
| **G6** 文档完整 | Day 12 | hard gate | ⬜ |
| **G7** MoE 可视化（v0.4 stretch）| Phase 2 | not required for v0.3 | ⬜ |

发版条件：G0-G6 全过。G7 不阻塞 v0.3。

---

## G0 · 环境就绪

**通过条件**

- `torch.cuda.is_available() == True`
- `torch.cuda.get_device_name(0)` 含 `NVIDIA`
- `transformers.__version__ >= 4.40`
- `accelerate` 可导入
- `~/.cache/huggingface` 可写 ∧ 磁盘空闲 > 5GB

**验证命令**

```powershell
python -c "
import torch, transformers, accelerate
import os, shutil
assert torch.cuda.is_available(), 'CUDA unavailable'
assert 'NVIDIA' in torch.cuda.get_device_name(0)
from packaging.version import Version
assert Version(transformers.__version__) >= Version('4.40'), transformers.__version__
hf_cache = os.path.expanduser('~/.cache/huggingface')
os.makedirs(hf_cache, exist_ok=True)
free_gb = shutil.disk_usage(hf_cache).free / 1e9
assert free_gb > 5, f'only {free_gb:.1f}GB free'
print('G0 PASS')
"
```

**失败应对**

- CUDA 不可用 → 重跑 Day 0.2（`pip install torch --index-url cu126`）
- transformers 版本太低 → `pip install -U transformers`
- HF cache 不可写 → 检查 PowerShell 权限或换路径（`HF_HOME=D:\hf_cache`）
- 磁盘 < 5GB → 清空 `~/.cache/huggingface/hub/` 中的旧模型

---

## G1 · 烟雾测试通过

**通过条件**

- `python scripts/lab_smoke.py` 退出码 0
- 模型加载成功
- 5 个 demo prompt 单次 forward `max_latency < 500ms`
- 一个 axis vector 构建成功
- 正面 prompt 投影 > 负面 prompt（sign check）
- GPU 显存峰值 < 7GB

**验证命令**

```powershell
python scripts/lab_smoke.py
echo "Exit code: $LASTEXITCODE"
```

**失败应对**

- 模型加载报 SSL / timeout → 设环境变量 `HF_ENDPOINT=https://hf-mirror.com`（国内镜像）
- 单 prompt latency > 1s → 检查 `torch.cuda.is_available()`；若 CPU fallback 回 G0
- GPU OOM → 关闭其他 GPU 进程；或 prompt 截断 `max_length=256`
- 投影方向反 → 不阻塞 G1，记到 risk log，等 G3 用更多数据判定

---

## G2 · 向量预计算 + 持久化

**通过条件**

- 4 个 axis vector 全构建成功（REASONING_BUDGET / SELF_VERIFICATION / TASK_WIDTH / SYCOPHANCY）
- `lab_vectors/r1_distill_1.5b_v1.pt` 文件大小 < 100MB
- 反序列化后投影结果与原始向量一致（`torch.allclose(reload_v, original_v)`）
- 包含 metadata：模型名、layer、构建时间、torch 版本、对数

**验证命令**

```powershell
python scripts/build_lab_vectors.py
python -c "
from stateprobe.lab.cache import LabVectorStore
import os
path = 'lab_vectors/r1_distill_1.5b_v1.pt'
size_mb = os.path.getsize(path) / 1e6
assert size_mb < 100, f'{size_mb:.1f}MB > 100MB'
store = LabVectorStore.load(path)
assert len(store.vectors) == 4, len(store.vectors)
print(f'G2 PASS: {len(store.vectors)} axes, {size_mb:.1f}MB')
"
```

**失败应对**

- 文件 > 100MB → 检查是否误存了整个 hidden state 而非方向（`vec.vector` 应该是 `(hidden_dim,)` shape）
- 反序列化数值不一致 → 检查 torch 版本兼容性，可能要存 numpy.float32 而非 torch tensor

---

## G3 · 区分度验证（hardest gate）

**通过条件**

- `docs/archive/v0.3/discrim_report.md` 提交
- 5 examples × 4 axes 三层对比表完整
- **至少 2 个 case 存在「lab 与 static/LLM 有意义分歧」**
  - 「有意义」定义：lab 的 normalized_score 与 static/LLM aggregate score 差 > 0.20
  - 且该差异有可解释的来源（不是噪声）
- 每个分歧 case 写一段简要分析

**验证命令**

```powershell
python scripts/discrim_table.py
# 看 docs/archive/v0.3/discrim_report.md 末尾的 G3 evaluation 段
```

**失败应对（分歧不足）**

1. **第 1 次失败**：换 layer。默认 `layer=-1`（最后一层），试 `layer=-8` 或 `layer=-16`（中间层）。Persona Vectors 论文建议中间层信号更强。
2. **第 2 次失败**：重新设计 contrastive pairs。当前 pairs 可能太"工程化"，缺乏真实用户措辞。
3. **第 3 次失败**：承认 Persona Vectors 方法在 1.5B distilled 模型上不够强。降级方案：
   - 不再 ship `LabContributor` as evidence layer
   - 改 ship 为「研究/调试工具」：提供 `stateprobe lab-probe PROMPT` 命令打印投影数字，不进 hybrid pipeline
   - v0.3 范围降级为「lab dataset + 复现脚本 + 诚实报告」
   - 文章公开承认「我们试过 Persona Vectors，在 1.5B distilled 上信号偏弱，需要 V2-Lite 或更大模型」——这本身就是 DeepSeek 团队会关心的诚实数据

---

## G4 · 三层 hybrid 集成

**通过条件**

- `stateprobe check examples/bad_sycophant.txt --llm-augment --lab-augment` 端到端 0 报错
- `stateprobe check examples/good_calm_reasoning.txt --lab-augment` 不破坏 trivial 检测
- `--lab-augment` 不需要时不加载模型（lazy init）
- LabContributor 不可用时（向量文件缺失 / 模型加载失败）silently drop，不阻塞 static + LLM

**验证命令**

```powershell
# 3 层 hybrid 不报错
stateprobe check examples/bad_sycophant.txt --llm-augment --lab-augment
# trivial 仍然检测正确
echo "你好" | stateprobe check - --lab-augment
# 故意删向量文件，验证降级
Move-Item lab_vectors/r1_distill_1.5b_v1.pt lab_vectors/_temp.pt
stateprobe check examples/bad_sycophant.txt --lab-augment 2>&1 | Select-String "lab.*unavailable|降级"
Move-Item lab_vectors/_temp.pt lab_vectors/r1_distill_1.5b_v1.pt
```

**失败应对**

- 3 层报错 → 检查 LabContributor.contribute() 返回类型是否符合 EvidenceContributor 协议
- trivial 假阳性 → 检查 confidence 阈值 `MIN_LAB_CONFIDENCE` 是否合适（默认 0.10，Day 4 经验校准）
- 降级不工作 → 确认 `EngineUnavailable` 异常被正确捕获

---

## G5 · 测试套件全绿

**通过条件**

- `pytest -q` 全绿
- 测试数 ≥ 122（v0.2 baseline 108 + ≥14 新 lab/visibility/CLI 测试；当前 153，含 +14 LLM panel UX regression）
- `python scripts/acceptance_check.py` 0 failures, 0 warnings
- `python scripts/acceptance_v02_stress.py` 仍 PASS（v0.2 backward compat 未破）

**验证命令**

```powershell
pytest -q
python scripts/acceptance_check.py
python scripts/acceptance_v02_stress.py
```

**失败应对**

- 老测试挂 → 不要为了过新功能改老测试。回滚 lab 改动，重新做 minimal diff
- 新测试覆盖率 < 80% → 补 unit test（重点：confidence gating、模型 lazy init、降级路径）

---

## G6 · 文档完整

**通过条件**

- `docs/archive/v0.3/EXECUTION.md`（本文档存在前置文档）
- `docs/archive/v0.3/TECHNICAL.md`
- `docs/archive/v0.3/PROJECT.md`
- `docs/archive/v0.3/ACCEPTANCE.md`（本文档）
- `docs/adr/010-lab-contributor.md`（状态 Accepted）
- `README.md` 含 "Activation probing" 小节
- `CHANGELOG.md` 含 0.3.0 完整条目
- `docs/archive/v0.3/reproducibility.md`：英文单页可贴 HN
- `docs/archive/v0.3/discrim_report.md`：G3 结果归档
- 所有 internal link 不 404

**验证命令**

```powershell
$docs = @(
  "docs/archive/v0.3/EXECUTION.md",
  "docs/archive/v0.3/TECHNICAL.md",
  "docs/archive/v0.3/PROJECT.md",
  "docs/archive/v0.3/ACCEPTANCE.md",
  "docs/adr/010-lab-contributor.md",
  "docs/archive/v0.3/reproducibility.md",
  "docs/archive/v0.3/discrim_report.md"
)
$docs | ForEach-Object { Test-Path $_ } | Where-Object { $_ -eq $false }
# 应该没有输出（全都存在）
Select-String -Path README.md -Pattern "Activation probing"
Select-String -Path CHANGELOG.md -Pattern "^## 0.3.0"
```

---

## G7 · MoE 可视化（v0.4 stretch，不阻塞 v0.3）

**通过条件**（仅当 Phase 2 启动后才评估）

- V2-Lite 在云 GPU 上加载成功
- 至少 1 个 expert routing heatmap 可视化产出
- expert routing 在 contrastive pair 上有可观测的差异（差异 > 30% 的 top-k expert 不重叠）
- 英文 deep-dive 博客发布
- HN Show 或 r/LocalLLaMA 发帖完成

不属于 v0.3 发版必需。

---

## 最终 sign-off 检查表

发版前 final check：

```powershell
# 1. 所有 hard gate 过
foreach ($g in 0..6) {
  Write-Host "G$g status: " -NoNewline
  # ... 各自验证
}

# 2. git status 干净
git status -s

# 3. tag 准备好
git tag -l "v0.3.0"

# 4. CHANGELOG 日期填了
Select-String -Path CHANGELOG.md -Pattern "## 0.3.0 - 2026-"
```

通过 7 项 hard gate + 干净 git + tag 后才发版。
