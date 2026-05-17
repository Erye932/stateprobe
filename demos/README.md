# StateProbe Demo Prompts

这里放的是可直接运行的验收 demo。

## 0. 看起来聪明，但没真正回答

```bash
stateprobe check --file demos/smart_but_not_answering/bad_prompt.txt
stateprobe eval run --original-file demos/smart_but_not_answering/bad_prompt.txt --rewritten-file demos/smart_but_not_answering/good_prompt.txt
```

## 1. 项目决策

```bash
stateprobe check --file demos/project_decision/bad_prompt.txt
stateprobe eval run --original-file demos/project_decision/bad_prompt.txt --rewritten-file demos/project_decision/good_prompt.txt
```

## 2. 代码生成

```bash
stateprobe check --file demos/code_generation/bad_prompt.txt
stateprobe eval run --original-file demos/code_generation/bad_prompt.txt --rewritten-file demos/code_generation/good_prompt.txt
```

## 3. 教学解释

```bash
stateprobe check --file demos/teaching/bad_prompt.txt --target teaching
stateprobe eval run --original-file demos/teaching/bad_prompt.txt --rewritten-file demos/teaching/good_prompt.txt
```

`eval run` 需要 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`。
