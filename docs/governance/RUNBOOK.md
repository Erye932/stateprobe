# StateProbe Runbook

操作手册。出事时翻这里。**不讲为什么，只讲做什么、按什么顺序**。

---

## 目录

- [1. 日常操作](#1-日常操作)
- [2. 发版 SOP](#2-发版-sop)
- [3. 发版回滚](#3-发版回滚)
- [4. 平台发布 SOP](#4-平台发布-sop)
- [5. 工程标准验收 gate](#5-工程标准验收-gate)
- [6. 平台合规 + 火热潜力 gate](#6-平台合规--火热潜力-gate)
- [7. 故障处理](#7-故障处理)
- [8. 监控指标](#8-监控指标)
- [9. 应急联系](#9-应急联系)

---

## 1. 日常操作

### 1.1 每日开始

```powershell
# 工作目录
cd D:\projects\stateprobe

# 拉远端最新（如有协作）
git pull --rebase

# 跑测试看上次是不是绿
python -m pytest -q
```

如果测试不绿，先修测试再开新工作。**绝不在红色基础上加东西**。

### 1.2 每日结束

```powershell
# 看 today 改了什么
git status
git diff --stat

# 跑全套验证
python -m pytest -q
python scripts/acceptance_check.py

# 全绿就 commit
git add -A
git commit -m "<type>(<scope>): <subject>"
git push
```

如果今天还没完成的，写到 `progress.txt`（gitignored）让明天的自己快速进入状态。

### 1.3 每周末复盘

每周日花 30 分钟：

1. 看本周 GitHub star / issue / 流量
2. 对照 [战略蓝图](C:/Users/Administrator/Desktop/stateprobe_blueprint.md) 第 6 节里程碑表
3. 写一条到 `docs/governance/PUBLIC_LOG.md`（公开日志）
4. 调整下周优先级

---

## 2. 发版 SOP

### 2.1 发版前 checklist（必须 100% 打勾才发）

```
[ ] 所有 P0/P1 bug 已修
[ ] python -m pytest -q  → 全绿
[ ] python scripts/acceptance_check.py → Acceptance passed
[ ] python scripts/acceptance_v02_stress.py → 4 个 v0.2 bug 都 fixed
[ ] CHANGELOG.md 当前版本章节完整
[ ] README.md 与新功能一致（命令示例真能跑）
[ ] pyproject.toml 版本号已更新（去掉 .devN 后缀）
[ ] docs/ARCHITECTURE.md 与代码架构一致
[ ] git status 干净（无未提交改动）
[ ] git pull --rebase 成功（无冲突）
```

**任何一条不打勾 = 不发**。

### 2.2 发版步骤（v0.2.0 为例）

```powershell
# Step 1: 改版本号
# 编辑 pyproject.toml: version = "0.2.0"
# 编辑 stateprobe/__init__.py: __version__ = "0.2.0"

# Step 2: commit 版本号
git add pyproject.toml stateprobe/__init__.py
git commit -m "chore: bump version to 0.2.0"

# Step 3: 跑全套验证
python -m pytest -q
python scripts/acceptance_check.py
python scripts/acceptance_v02_stress.py

# Step 4: 打 tag
git tag -a v0.2.0 -m "v0.2.0 - Hybrid Evidence Engine"
git push origin main
git push origin v0.2.0

# Step 5: 在 GitHub 上 Create Release
# 标题: v0.2.0 - Hybrid Evidence Engine
# 正文: 复制 CHANGELOG 当前版本章节 + Article 链接
# 上传: 不需要预编译产物（pip install -e . 就能用）

# Step 6: 在 README 里把 "Latest: v0.x" 字段更新（如果有）

# Step 7: 准备 .dev0 后缀给下一个版本
# pyproject.toml: version = "0.3.0.dev0"
# stateprobe/__init__.py: __version__ = "0.3.0.dev0"
git add pyproject.toml stateprobe/__init__.py
git commit -m "chore: start v0.3 dev cycle"
git push
```

### 2.3 发版后 24 小时观察

```
[ ] GitHub release 显示在 Releases tab
[ ] pip install git+ssh://...stateprobe.git@v0.2.0 能装
[ ] stateprobe demo 在干净环境能跑
[ ] 关注 issue 区，回复必出 24 小时内
[ ] X / 知乎平台帖发出，监控评论
```

---

## 3. 发版回滚

如果发了 v0.2.0 后 24 小时内发现严重问题：

### 3.1 评估损害

| 严重度 | 描述 | 应对 |
|---|---|---|
| **P0 致命** | 装上 import 失败 / `stateprobe demo` 直接挂 | 立即回滚 + 紧急修复 v0.2.1 |
| **P1 严重** | 主流程报错但 demo 能跑 | 在 issue / release 顶部贴说明，2 天内 v0.2.1 |
| **P2 中等** | 边缘 bug，绕得开 | 进 v0.3 计划，不紧急 |
| **P3 小** | 文档错别字 / 显示问题 | 攒着一起改 |

### 3.2 P0 回滚步骤

```powershell
# 1. 在 GitHub Release 页把 v0.2.0 标记为 "Pre-release" 或直接删
# 2. 删 tag
git tag -d v0.2.0
git push origin :refs/tags/v0.2.0

# 3. 修代码（紧急）
# ... edit files ...

# 4. 走 §2.2 步骤发 v0.2.1，CHANGELOG 注明 "Hotfix for v0.2.0 critical bug XYZ"

# 5. 在 issue 区开置顶 issue，告诉用户跳过 v0.2.0 直接装 v0.2.1
```

### 3.3 沟通模板

GitHub 公告：

```markdown
## ⚠️ v0.2.0 has been pulled due to critical bug XXX

If you installed v0.2.0, please upgrade to v0.2.1:

```bash
pip install --upgrade git+ssh://...stateprobe.git@v0.2.1
```

Apologies for the noise. Postmortem coming in 24h.
```

知乎 / X 同步发简短说明，不藏。

---

## 4. 平台发布 SOP

### 4.1 v0.2 发版后的 7 天发布节奏

| Day | 平台 | 内容 | 预估时间 |
|---|---|---|---|
| D0 | GitHub | Release + 锁住 v0.2.0 tag | 30 min |
| D0 | 知乎 | 发 article_zhihu_v2.md（重写后版本） | 30 min |
| D0+12h | X | 发 v0.2 序列第 1 帖（功能介绍） | 10 min |
| D1 | X | 发第 2 帖（DeepSeek 物理优势） | 10 min |
| D1 | 小红书 | 发图文短版（500 字 + 4 图） | 30 min |
| D2 | 微信公众号 | 知乎转载 | 20 min |
| D2 | X | 发第 3 帖（路线图） | 10 min |
| D5 | HN | 发 Show HN（待版本稳定 1 周） | 20 min |
| D7 | 各平台 | 复盘流量数据，决定下一步 | 1 h |

### 4.2 单平台发布 micro-SOP

#### 知乎发文

```
1. 把 article_zhihu_v2.md 用预览工具看一遍渲染（VS Code 或 Typora）
2. 走 §6 平台合规 + 火热潜力 gate
3. 知乎 PC web 登录，新建文章
4. 标题 ≤ 30 字，含数字或对比（如 "我写了 89 行代码诊断 prompt 行为状态"）
5. 粘贴正文（Markdown 知乎自动识别）
6. 检查 Mermaid 图渲染情况；不行则换 PNG（docs/images/ 下的）
7. 标签：AI / 大语言模型 / DeepSeek / 开源 / 工程实践（5 个为限）
8. 发布
9. 24 小时内监控：
   - 阅读量
   - 点赞 / 收藏
   - 评论质量（高质量评论优先回，10 字内不回）
   - 引到 GitHub 的 referrer
```

#### X 发帖

```
1. 帖子草稿用英文（受众主要是国际开发者）
2. 字符 ≤ 280
3. 1 个截图或 GIF
4. 至多 3 个 hashtag（#DeepSeek #LLM #OpenSource 是首选）
5. 不 @ 大账号请求转发（被识别为 spam）
6. 走 §6 gate
7. 发布
8. 1 小时内回复早期评论
```

#### Hacker News Show HN

```
1. 标题: "Show HN: StateProbe – diagnose what your prompt activates in DeepSeek"
2. 标题 ≤ 80 字符，不带 emoji，不夸张
3. 第一条评论自己发：技术细节 + 限制说明（HN 文化喜欢谦虚）
4. 不 @ 朋友，不刷票（HN 反作弊会降权）
5. 美东时间周二/周三早 8-10 点发（流量峰）
6. 24 小时内积极回复每条评论
```

#### 小红书发图文

```
1. 标题: 6-10 字，带 emoji（小红书算法偏爱）
   例: "我写了个工具帮你看懂 prompt"
2. 正文 ≤ 500 字，分点写
3. 4-9 张图（封面 + 内容图）
4. 不放 GitHub 链接（会限流），引到个人简介
5. 标签：#AI #大模型 #程序员 #工具推荐
6. 发布时段：晚 20-22 点最佳
```

### 4.3 平台流量来源跟踪

GitHub Insights → Traffic 看 referrer。每周记录到 `docs/governance/PUBLIC_LOG.md`。

格式：

```markdown
## 2026-W21
- 知乎 v2 文章发布 → 阅读 1500 / star +30
- X 序列 → 50 站外点击 / star +5
- HN Show → 暂未发
- 总 star 增量: +35（新 base: 135）
```

---

## 5. 工程标准验收 gate

每个交付物必过这道 gate 才算"完成"。

### 5.1 代码层验收

| 项 | 标准 | 检查方法 |
|---|---|---|
| 单元测试 | 100% pass | `python -m pytest -q` |
| 类型注解 | 公共 API 必须有 | 人工 review |
| Docstring | 公共 API 必须有 | 人工 review |
| Acceptance check | 100% pass | `python scripts/acceptance_check.py` |
| 性能不回归 | static-only 诊断 < 50ms | `python -c "import time; from stateprobe import diagnose; t=time.time(); diagnose('test'); print(time.time()-t)"` |
| 无新警告 | pytest 不报 deprecation / warning | `python -m pytest -W error` |

### 5.2 文档层验收

| 项 | 标准 |
|---|---|
| README 与代码一致 | 所有命令示例能直接跑通 |
| CHANGELOG 完整 | 当前版本 Added/Changed/Fixed 三类必齐 |
| 架构文档同步 | docs/ARCHITECTURE.md 与代码组织一致 |
| ADR 落地 | 每个重大决策都有对应 docs/adr/NNN-xxx.md 或 docs/adr/decisions.md 条目 |
| 链接有效 | 所有 markdown 内部链接可点击 |

### 5.3 测试层验收

| 项 | 标准 |
|---|---|
| 覆盖率 | 核心模块（detector/rules/engines）≥ 80% |
| 边界用例 | 空输入 / 巨长输入 / Unicode / 多语言 都有测试 |
| Regression | 每个修过的 bug 必有对应测试 |
| 集成测试 | hybrid 三种场景（static-only/llm-only-fake/both）都有 |

### 5.4 验收命令一行版

```powershell
python -m pytest -q && python scripts/acceptance_check.py && Write-Host "ALL GREEN"
```

---

## 6. 平台合规 + 火热潜力 gate

每篇公开内容（文章 / 长帖 / 视频脚本）发布前必过。

### 6.1 平台合规清单

| 平台 | 必查项 |
|---|---|
| 知乎 | 不过度自荐 / 标题非震惊体（"震惊"/"必看"/"刷屏"禁用）/ 不点名贬损友商 / 不涉政治宗教民族敏感 |
| X | 字符 ≤ 280 / hashtag ≤ 3 / 不 @ 大账号请求 RT / 图片 alt text 完整 |
| HN | 标题 ≤ 80 / 不带 emoji / 不带营销词（best/awesome/revolutionary 禁用）/ Self-promotion 比例 < 1:9（即 9 条社区互动 + 1 条自推） |
| 小红书 | 不放外站链接 / 标签合规（避开违禁词）/ 图片清晰 / 不诱导分享 |
| 微信 | 不诱导分享 / 不违反平台规范（参考最新版） / 商业内容标注 |
| GitHub | README 不含夸张词（"world's best" 等）/ License 清楚 / 描述准确 |
| B 站 | 标题 ≤ 80 / 封面无诱导 / 标签 ≤ 10 |
| Reddit | 遵守目标 sub 的规则 / 自推不超过该 sub 限制 / 标题客观 |

### 6.2 火热潜力评分（每项 0-2 分）

满分 14。**< 10 分必须重写**。≥ 12 分有较高爆发可能。

| 维度 | 0 分 | 1 分 | 2 分 |
|---|---|---|---|
| **钩子（前 3 行）** | 平铺直叙 | 提了个问题 | 强烈反差 / 情绪 / 出乎意料 |
| **具体性** | 全抽象概念 | 1-2 个具体例子 | 例子贯穿全文 |
| **可视化** | 纯文字 | 1-2 张截图 | 图 + 流程图 + 表格俱全 |
| **强观点** | 无观点 | 温和观点 | 有受争议但论据充分 |
| **实操价值** | 看完啥用都没 | 学到一点 | 立即可用 |
| **故事性** | 平铺直叙 | 有时间线 | 有冲突有反转 |
| **CTA 转化** | 无 / 弱 | 有 CTA | 强 CTA + 路径清晰 |

### 6.3 给 article_zhihu_v2.md 评分（hybrid 重写后预期）

| 维度 | 自评 | 提分点 |
|---|---|---|
| 钩子 | 1 | 加强首段（如 "我做错了一版架构，公开复盘"） → 2 |
| 具体性 | 2 | 已贯穿坏 prompt → 诊断 → 改写 |
| 可视化 | 2 | 加 4 张图 |
| 强观点 | 2 | "DeepSeek 是物理上唯一能做这事的模型" |
| 实操 | 2 | 30 秒上手 |
| 故事 | 2 | v0.1→v0.2 演进 + 走过弯路 |
| CTA | 1 | GitHub 链接 + Star CTA |

预期 12 分，可发。

### 6.4 给 X 帖评分

每条 X 帖单独评分。例：

**帖 1 草稿**:
> StateProbe v0.2 ships hybrid evidence engine.
> Static rules + LLM judge contribute evidence into the same axis pool, no more either-or.
> Built specifically for DeepSeek's open MoE — something OpenAI's models physically can't support.
> https://github.com/Erye932/stateprobe

| 维度 | 评 |
|---|---|
| 钩子 | 1 |
| 具体性 | 1（hybrid 描述抽象） |
| 可视化 | 0（要加图） |
| 强观点 | 2（OpenAI 那句对比） |
| 实操 | 1（链接给了） |
| 故事 | 0 |
| CTA | 1（链接是隐 CTA） |

预期 6 分。**重写**：加架构图、加具体 bug 案例。

---

## 7. 故障处理

### 7.1 常见问题

#### CLI 显示乱码（PowerShell）

```powershell
# 临时修复
chcp 65001

# 永久修复（在 PS profile 里）
notepad $PROFILE
# 加这行: chcp 65001 | Out-Null
```

#### LLM 引擎 EngineUnavailable

按顺序检查：

```powershell
# 1. API key 是否设置
$env:DEEPSEEK_API_KEY

# 2. 网络是否通
Test-NetConnection api.deepseek.com -Port 443

# 3. 直接 curl 验证 key
curl https://api.deepseek.com/v1/models -H "Authorization: Bearer $env:DEEPSEEK_API_KEY"

# 4. 看错误日志
python -m stateprobe.cli check --llm-augment --verbose "test"
```

#### 测试在 CI 上 fail 但本地过

```powershell
# 强制 UTF-8
$env:PYTHONIOENCODING = "utf-8"

# 确认 Python 版本一致
python --version

# 重装确认依赖完整
pip install -e ".[dev]" --force-reinstall
```

#### Git push 被拒（pre-receive hook）

通常是 GitHub secret scanning 检测到泄露。

```powershell
# 看哪个 commit 含敏感信息
git log -p --all -S "DEEPSEEK_API_KEY" -- .

# 用 git-filter-repo 清理（先备份！）
git clone <repo> backup-repo
cd repo
git filter-repo --replace-text replacements.txt
git push --force-with-lease
```

### 7.2 GitHub 访问问题（中国大陆）

```powershell
# SSH over 443 端口（绕 GFW）
git clone ssh://git@ssh.github.com:443/Erye932/stateprobe.git

# 或在 ~/.ssh/config 加：
# Host github.com
#     Hostname ssh.github.com
#     Port 443
#     User git
```

### 7.3 知乎被限流

症状：发文 24h 后阅读量 < 100

可能原因：
- 标题/内容触发了关键词
- 链接太多（GitHub 链接放评论区）
- 标签错配（5 个标签全部要相关）

应对：
- 修改文章去掉外链 / 高密度产品名
- 评论区补 GitHub 链接
- 等 48h 看是否恢复，无则迁移到知乎答主回答相关问题（不发新文）

---

## 8. 监控指标

### 8.1 每日

| 指标 | 来源 | 目标 |
|---|---|---|
| GitHub star 总数 | github.com/Erye932/stateprobe | 增长 ≥ 0 |
| 新 issue 数 | GitHub issue tab | 24h 内回复 |
| X 帖 impression | X analytics | 平均 ≥ 500 |

### 8.2 每周

| 指标 | 来源 | 目标 |
|---|---|---|
| GitHub Insights → Visitors | GitHub | 周环比正向 |
| GitHub Insights → Clones | GitHub | ≥ 5/周 |
| 知乎文章阅读量 | 知乎 | 单篇 ≥ 1000 |
| 测试覆盖率 | pytest --cov | ≥ 80% |
| commit 频率 | `git log --since="1 week ago" --oneline` | ≥ 5 |

### 8.3 每月

| 指标 | 来源 | 目标 |
|---|---|---|
| star 净增 | GitHub | M1: +100 / M2: +200 / M3: +500 |
| 企业内测意向 | issue + 邮箱 | M1: 1 / M2: 3 / M3: 5 |
| 文章总曝光 | 各平台 | ≥ 10K |
| 重大风险信号 | 战略蓝图 §4 | 0 |

---

## 9. 应急联系

### 9.1 关键资源 URL

- GitHub repo: https://github.com/Erye932/stateprobe
- GitHub issues: https://github.com/Erye932/stateprobe/issues
- 知乎主页: （待填）
- X handle: @Erye932
- 邮箱（issue 兜底）: （待填）

### 9.2 关键文档优先级

出问题翻顺序：
1. 当前 RUNBOOK.md（你正在看的）
2. [DEVELOPMENT.md](../DEVELOPMENT.md)（开发流程）
3. [战略蓝图](C:/Users/Administrator/Desktop/stateprobe_blueprint.md)（产品方向）
4. [ADR_009](../adr/009-hybrid-engine.md)（架构决策）
5. [decisions.md](../adr/decisions.md)（其他决策）

### 9.3 紧急升级路径

| 情况 | 立即做 |
|---|---|
| 安全漏洞被报告 | 24h 内 patch + Security Advisory |
| API key 泄露 | 立即 revoke + 重新 issue + 公开说明 |
| DeepSeek 出官方解释器 | 当天读 §4.3 战略蓝图，48h 内决定方向 |
| GitHub 仓库被锁 | 联系 GitHub support + 准备 mirror（GitLab/Gitee） |

---

*这份文档是给"出事时的你"看的。日常不用读完。*
