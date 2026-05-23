# StateProbe 发布前检查清单

这个清单用来判断项目是否可以发 GitHub / PyPI。

## 1. 产品验收

- [ ] 我能用一句话解释 StateProbe：给 agent 的注意力控制台，先让输出方向可见，再决定继续、重写、追问或切旧上下文
- [ ] README 第一屏明确：Skill 已可用，Runtime Probe 是长期方向
- [ ] 至少跑通一次 `stateprobe skill preview`
- [ ] 至少跑通一次 `stateprobe skill overlay`
- [ ] 至少看过 `docs/SKILL_ATTENTION_HUD.md`
- [ ] 至少看过 `docs/MCP_SERVER.md`
- [ ] `docs/governance/PROJECT_BRIEF.md` 看得懂
- [ ] `docs/DEMO_WALKTHROUGH.md` 的 3 个 demo 看得懂
- [ ] 至少跑通一个 `stateprobe check` demo
- [ ] 至少生成一次 HTML report
- [ ] 至少跑通一次 `stateprobe eval run` DeepSeek black-box eval

## 2. 工程验收

- [ ] `python -m pytest tests/ -q` 全部通过
- [ ] `stateprobe --help` 正常
- [ ] `stateprobe skill --help` 正常
- [ ] `stateprobe skill preview --help` 正常
- [ ] `stateprobe skill overlay --help` 正常
- [ ] `stateprobe-mcp` 能被安装出来
- [ ] `stateprobe check --help` 正常
- [ ] `stateprobe eval run --help` 正常
- [ ] `.gitignore` 包含 `.env`、`.env.*`、`*.key`
- [ ] 没有把 API key 写进代码或文档

## 3. 文档验收

- [ ] README 第一屏能说明项目价值
- [ ] README 有安装方式
- [ ] README 有 Skill 最小使用示例
- [ ] README 有 MCP 安装说明
- [ ] README 有 DeepSeek Lab / Black-box Eval 说明
- [ ] README 明确说明 API key 使用环境变量
- [ ] README 的 GitHub URL 已换成真实地址
- [ ] `docs/ENTERPRISE_RUNTIME_PROBE.md` 没有暗示 Runtime Probe 已实现

## 4. GitHub 发布

- [ ] `git init`
- [ ] `git add .`
- [ ] `git commit -m "Initial StateProbe MVP"`
- [ ] 创建 GitHub repo
- [ ] 推送到远程仓库
- [ ] 检查 GitHub 页面 README 渲染正常

## 5. PyPI 发布（可选）

- [ ] 安装 build 工具：`python -m pip install build twine`
- [ ] 构建包：`python -m build`
- [ ] 检查包：`python -m twine check dist/*`
- [ ] 先发 TestPyPI
- [ ] 再发正式 PyPI

## 6. 暂时不做的事

这些不是 V0.1 必须项：

- [ ] VS Code / Cursor 插件
- [ ] 用户自定义规则 DSL
- [ ] DeepSeek hidden-state 大规模校准
- [ ] Web UI
- [ ] 商业化后台

## V0.1 发布标准

如果以下 5 条满足，就可以发 GitHub：

1. 测试全过
2. README 看得懂
3. Skill / MCP 最小路径能跑
4. 没泄露 API key
5. 项目边界讲清楚
