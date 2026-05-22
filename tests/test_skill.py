import json

import pytest
from click.testing import CliRunner

from stateprobe.cli import main
from stateprobe.skill import analyze_attention, extract_requirements, preview_attention


def test_extract_requirements_detects_chinese_positive_and_negative_markers():
    reqs = extract_requirements(
        "核心是让agent的注意力可见。不要把格式化当主线。必须先做skill再做企业线。"
    )

    by_text = {req.text: req for req in reqs}

    assert by_text["核心是让agent的注意力可见"].polarity == "must"
    assert by_text["不要把格式化当主线"].polarity == "must_not"
    assert by_text["必须先做skill再做企业线"].polarity == "must"


def test_analyze_attention_flags_ignored_focus_and_high_drift():
    hud = analyze_attention(
        "我要做一个GitHub开源项目。\n"
        "核心是让agent的注意力可见。\n"
        "不要把格式化当主线。\n"
        "必须先做skill再做企业线。\n"
        "重点是注意力仪表盘，不是prompt检查器。",
        "StateProbe是一个prompt检查器，它通过正则规则分析prompt结构，"
        "帮助你优化输出格式，并提供丰富的格式化模板。企业版即将上线。",
    )

    ignored_texts = {item.requirement.text for item in hud.ignored}
    weak_texts = {item.requirement.text for item in hud.weak}

    assert hud.drift_level == "high"
    assert "核心是让agent的注意力可见" in ignored_texts
    assert "必须先做skill再做企业线" in ignored_texts
    assert "不要把格式化当主线" in weak_texts
    assert any("核心是让agent的注意力可见" in line for line in hud.next_turn_patch)


def test_analyze_attention_flags_negative_requirement_violation():
    hud = analyze_attention(
        "不要做前端界面。",
        "我建议我们做一个漂亮的前端界面。",
    )

    violated_texts = {item.requirement.text for item in hud.violated}

    assert "不要做前端界面" in violated_texts
    assert hud.drift_level in {"medium", "high"}
    assert any("不要做前端界面" in line for line in hud.next_turn_patch)


def test_analyze_attention_low_drift_when_requirements_are_reflected():
    hud = analyze_attention(
        "核心是让agent的注意力可见。必须先做skill再做企业线。",
        "核心是让agent的注意力可见。必须先做skill再做企业线。"
        "我们用HUD显示用户要求是否被回应。",
    )

    reflected_texts = {item.requirement.text for item in hud.reflected}

    assert "核心是让agent的注意力可见" in reflected_texts
    assert "必须先做skill再做企业线" in reflected_texts
    assert hud.drift_level == "low"
    assert hud.next_turn_patch == []


def test_analyze_attention_reflects_negative_requirement_when_avoided():
    hud = analyze_attention(
        "不要做前端界面。",
        "我们先实现命令行Skill入口和核心注意力判断逻辑。",
    )

    reflected_texts = {item.requirement.text for item in hud.reflected}

    assert "不要做前端界面" in reflected_texts
    assert hud.violated == []


def test_attention_hud_to_dict_is_json_serializable():
    hud = analyze_attention(
        "Core focus must be agent attention visibility. Do not make formatting the main story.",
        "This project is mainly a formatting helper with templates.",
    )

    payload = hud.to_dict()
    encoded = json.dumps(payload, ensure_ascii=False)
    decoded = json.loads(encoded)

    assert decoded["drift_level"] in {"low", "medium", "high"}
    assert "next_turn_patch" in decoded
    assert "notes" in decoded


def test_skill_overlay_cli_json_output_is_parseable(tmp_path):
    context = tmp_path / "context.txt"
    output = tmp_path / "output.txt"
    context.write_text(
        "核心是让agent的注意力可见。不要把格式化当主线。必须先做skill再做企业线。",
        encoding="utf-8",
    )
    output.write_text(
        "这是一个prompt检查器，用正则规则帮助你优化格式化模板。",
        encoding="utf-8",
    )

    result = CliRunner().invoke(main, [
        "skill",
        "overlay",
        "--context",
        str(context),
        "--output",
        str(output),
        "--json",
    ])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["drift_level"] in {"medium", "high"}
    assert payload["ignored"]
    assert payload["next_turn_patch"]


def test_skill_overlay_cli_control_patch_outputs_plain_text(tmp_path):
    context = tmp_path / "context.txt"
    output = tmp_path / "output.txt"
    context.write_text(
        "核心是让agent的注意力可见。必须先做skill再做企业线。",
        encoding="utf-8",
    )
    output.write_text(
        "我们先做企业版prompt检查器。",
        encoding="utf-8",
    )

    result = CliRunner().invoke(main, [
        "skill",
        "overlay",
        "--context",
        str(context),
        "--output",
        str(output),
        "--control-patch",
    ])

    assert result.exit_code == 0
    assert "下一轮" in result.output
    assert "核心是让agent的注意力可见" in result.output
    assert "{\n" not in result.output


def test_enterprise_runtime_probe_placeholder_fails_loudly():
    from stateprobe.enterprise import RuntimeProbe

    with pytest.raises(NotImplementedError, match="not implemented yet"):
        RuntimeProbe()


# ---------------------------------------------------------------------------
# Phase 7：注意力-输出控制 HUD
# ---------------------------------------------------------------------------

def test_phase7_user_intent_map_normalizes_weights_and_priorities():
    hud = analyze_attention(
        "核心是让agent的注意力可见。"
        "不要把格式化当主线。"
        "必须先做skill再做企业线。",
        "我们做一个prompt检查器。",
    )

    intents = hud.user_intent_map
    assert len(intents) == 3
    priorities = {i.priority for i in intents}
    assert "must" in priorities
    assert "must_not" in priorities
    total_weight = sum(i.weight for i in intents)
    assert 0.99 <= total_weight <= 1.01


def test_phase7_attention_map_marks_off_task_and_violation():
    hud = analyze_attention(
        "核心是让agent的注意力可见。不要把格式化当主线。",
        "StateProbe是一个prompt检查器，"
        "它通过格式化模板帮助你优化输出。"
        "格式化模板是核心，格式化模板要漂亮。",
    )

    alignments = {sig.alignment for sig in hud.agent_attention_map}
    # 格式化是 must_not 关键词，应被识别为 violation
    assert "violation" in alignments
    # 应该有未匹配任何要求的 off_task 落点（如 prompt / 检查器 / 模板）
    assert "off_task" in alignments


def test_phase7_attention_gaps_capture_missing_must():
    hud = analyze_attention(
        "核心是让agent的注意力可见。必须先做skill再做企业线。",
        "我们做一个完全无关的天气预报应用。",
    )

    kinds = {g.kind for g in hud.attention_gaps}
    assert "missing" in kinds
    high_severity = [g for g in hud.attention_gaps if g.severity == "high"]
    assert high_severity, "ignored 的 must 要求应当产生 high severity gap"


def test_phase7_output_trajectory_predicts_drift_direction():
    hud = analyze_attention(
        "核心是让agent的注意力可见。不要把格式化当主线。",
        "StateProbe是一个prompt检查器，"
        "它通过格式化模板帮助你优化输出。"
        "格式化模板是核心。",
    )

    traj = hud.output_trajectory
    assert traj is not None
    assert traj.risk in {"medium", "high"}
    assert traj.confidence in {"medium", "high"}
    # 既然存在 violation 或 off_task，likely_direction 必须是 *偏离* 方向
    assert "延续" in traj.likely_direction or "漏掉" in traj.likely_direction
    assert traj.why  # 至少一条解释


def test_phase7_control_levers_propose_boost_and_stop_doing():
    hud = analyze_attention(
        "核心是让agent的注意力可见。不要做前端界面。",
        "我建议我们做一个漂亮的前端界面。",
    )

    levers = hud.control_levers
    assert levers is not None
    # must 要求被忽略 → 必须有 boost / return_to
    assert any("注意力" in s for s in levers.boost)
    assert any("回到" in s for s in levers.return_to)
    # must_not 要求被违反 → 必须有 suppress / stop_doing
    assert any("前端" in s for s in levers.suppress)
    assert any("停止" in s for s in levers.stop_doing)


def test_phase7_interrupt_level_escalates_on_violation():
    hud_violation = analyze_attention(
        "不要做前端界面。",
        "我建议我们做一个漂亮的前端界面。",
    )
    hud_clean = analyze_attention(
        "核心是让agent的注意力可见。",
        "核心是让agent的注意力可见，我们用HUD显示用户要求。",
    )

    assert hud_violation.interrupt_level == "interrupt"
    assert hud_clean.interrupt_level == "ok"


def test_phase7_hud_to_dict_includes_new_fields_and_is_json_serializable():
    hud = analyze_attention(
        "核心是让agent的注意力可见。不要把格式化当主线。",
        "StateProbe是一个prompt检查器，格式化模板是核心。",
    )

    payload = hud.to_dict()
    encoded = json.dumps(payload, ensure_ascii=False)
    decoded = json.loads(encoded)

    for key in (
        "user_intent_map",
        "agent_attention_map",
        "attention_gaps",
        "output_trajectory",
        "control_levers",
        "interrupt_level",
    ):
        assert key in decoded
    assert decoded["interrupt_level"] in {"ok", "watch", "interrupt"}
    assert decoded["output_trajectory"] is not None
    assert decoded["output_trajectory"]["risk"] in {"low", "medium", "high"}


# ---------------------------------------------------------------------------
# Phase 9：零依赖 agent context API（直传 text / stdin JSON / 互斥校验）
# ---------------------------------------------------------------------------

def test_phase9_skill_overlay_accepts_inline_text_without_files():
    result = CliRunner().invoke(main, [
        "skill",
        "overlay",
        "--context-text",
        "核心是让agent的注意力可见。不要把格式化当主线。",
        "--output-text",
        "StateProbe是一个prompt检查器，格式化模板是核心。",
        "--json",
    ])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["drift_level"] in {"medium", "high"}
    assert payload["interrupt_level"] in {"watch", "interrupt"}
    assert payload["user_intent_map"]


def test_phase9_skill_overlay_accepts_stdin_json():
    stdin_payload = json.dumps({
        "context": "核心是让agent的注意力可见。必须先做skill再做企业线。",
        "output": "我们做一个完全无关的天气预报应用。",
    }, ensure_ascii=False)

    result = CliRunner().invoke(
        main,
        ["skill", "overlay", "--stdin-json", "--json"],
        input=stdin_payload,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["interrupt_level"] == "interrupt"
    assert payload["ignored"]
    assert any(
        g["kind"] == "missing" for g in payload["attention_gaps"]
    )


def test_phase9_skill_overlay_stdin_json_rejects_invalid_payload():
    result = CliRunner().invoke(
        main,
        ["skill", "overlay", "--stdin-json", "--json"],
        input="not a json at all",
    )

    assert result.exit_code != 0
    assert "stdin-json 解析失败" in result.output


def test_phase9_skill_overlay_stdin_json_rejects_missing_fields():
    result = CliRunner().invoke(
        main,
        ["skill", "overlay", "--stdin-json", "--json"],
        input=json.dumps({"context": "only context, no output"}),
    )

    assert result.exit_code != 0
    assert "context 和 output" in result.output


def test_phase9_skill_overlay_mutually_exclusive_sources(tmp_path):
    context = tmp_path / "ctx.txt"
    context.write_text("核心是让agent的注意力可见。", encoding="utf-8")

    # --context-text 与 --context 不能同时使用
    result_ctx = CliRunner().invoke(main, [
        "skill", "overlay",
        "--context", str(context),
        "--context-text", "另一段文本",
        "--output-text", "随便",
    ])
    assert result_ctx.exit_code != 0
    assert "--context 与 --context-text" in result_ctx.output

    # --stdin-json 不能与其它来源并用
    result_stdin = CliRunner().invoke(main, [
        "skill", "overlay",
        "--stdin-json",
        "--context-text", "x",
        "--output-text", "y",
    ], input='{"context":"x","output":"y"}')
    assert result_stdin.exit_code != 0
    assert "--stdin-json 不能" in result_stdin.output


def test_phase9_skill_overlay_missing_inputs_errors_clearly():
    result = CliRunner().invoke(main, ["skill", "overlay", "--json"])

    assert result.exit_code != 0
    # 任一缺失都要有清晰中文提示，不是隐式 None 崩溃
    assert "缺少用户上下文" in result.output or "缺少 agent 输出" in result.output


def test_phase9_skill_overlay_rejects_whitespace_only_text():
    # strip 后为空白也要按缺失处理，不能渲染空 HUD
    result_ctx = CliRunner().invoke(
        main,
        ["skill", "overlay", "--context-text", "   ", "--output-text", "ok"],
    )
    assert result_ctx.exit_code != 0
    assert "缺少用户上下文" in result_ctx.output

    result_out = CliRunner().invoke(
        main,
        ["skill", "overlay", "--context-text", "ok", "--output-text", "\t\n "],
    )
    assert result_out.exit_code != 0
    assert "缺少 agent 输出" in result_out.output


def test_phase12_must_not_boundary_does_not_render_function_word_ngrams():
    # README 推荐 demo 里这条 prompt 之前会渲染出 `不要把 / 要把格 / 把格式` 碎片
    preview = preview_attention(
        "核心是让 agent 的注意力可见。不要把格式化当主线。",
        "我准备重点写 prompt 检查器和格式化模板。",
    )
    must_not = {
        item["element"]
        for item in preview.to_dict()["boundary_decomposition"]["must_not_show"]
    }
    bad_fragments = {"不要把", "要把格", "把格式", "不要", "要把", "把格"}
    leaked = must_not & bad_fragments
    assert not leaked, f"must_not_show leaked function-word ngrams: {leaked}"
    # 至少要给出一个有意义的 3-gram；这里用 `格式化` 作为正面期望
    assert any(len(item) >= 3 for item in must_not), (
        f"must_not_show should contain a readable 3-gram, got: {must_not}"
    )


def test_phase11_skill_preview_rejects_whitespace_only_text():
    result_ctx = CliRunner().invoke(
        main,
        ["skill", "preview", "--context-text", "   ", "--plan-text", "ok"],
    )
    assert result_ctx.exit_code != 0
    assert "缺少用户上下文" in result_ctx.output

    result_plan = CliRunner().invoke(
        main,
        ["skill", "preview", "--context-text", "ok", "--plan-text", "\t\n "],
    )
    assert result_plan.exit_code != 0
    assert "缺少 planned focus" in result_plan.output


def test_phase7_skill_overlay_cli_json_carries_phase7_fields(tmp_path):
    context = tmp_path / "context.txt"
    output = tmp_path / "output.txt"
    context.write_text(
        "核心是让agent的注意力可见。不要把格式化当主线。",
        encoding="utf-8",
    )
    output.write_text(
        "StateProbe是一个prompt检查器，格式化模板是核心。",
        encoding="utf-8",
    )

    result = CliRunner().invoke(main, [
        "skill",
        "overlay",
        "--context",
        str(context),
        "--output",
        str(output),
        "--json",
    ])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["user_intent_map"]
    assert payload["agent_attention_map"]
    assert payload["control_levers"] is not None
    assert payload["output_trajectory"] is not None
    assert payload["interrupt_level"] in {"ok", "watch", "interrupt"}


# ---------------------------------------------------------------------------
# Phase 11：Opening Attention Preview（输出开头及时止损）
# ---------------------------------------------------------------------------

def test_phase11_preview_attention_interrupts_bad_planned_focus():
    preview = preview_attention(
        "核心是让agent的注意力可见。不要把格式化当主线。",
        "我准备重点写prompt检查器和格式化模板。",
    )

    assert preview.risk_level == "high"
    assert preview.should_continue is False
    assert preview.user_intent_map
    assert preview.planned_attention_map
    assert preview.missing_before_start
    assert any("开头先覆盖" in line for line in preview.opening_patch)
    assert any("注意力" in s for s in preview.control_levers.boost)
    assert preview.activation_decision.action == "rewrite_planned_focus"
    assert preview.activation_decision.should_stop is True


def test_phase11_preview_attention_allows_aligned_planned_focus():
    preview = preview_attention(
        "核心是让agent的注意力可见。不要把格式化当主线。",
        "我会先展示agent注意力可见HUD，再说明如何避免格式化成为主线。",
    )

    assert preview.risk_level in {"low", "medium"}
    assert preview.should_continue is True
    assert preview.to_dict()["planned_attention_map"]
    assert preview.activation_decision.action == "continue"
    assert preview.activation_decision.should_stop is False


def test_phase11_skill_preview_cli_json_accepts_inline_text():
    result = CliRunner().invoke(main, [
        "skill",
        "preview",
        "--context-text",
        "核心是让agent的注意力可见。不要把格式化当主线。",
        "--plan-text",
        "我准备重点写prompt检查器和格式化模板。",
        "--json",
    ])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["risk_level"] == "high"
    assert payload["should_continue"] is False
    assert payload["opening_patch"]
    assert payload["control_levers"]["boost"]


def test_phase11_skill_preview_cli_stdin_json_accepts_plan_alias():
    stdin_payload = json.dumps({
        "context": "核心是让agent的注意力可见。不要把格式化当主线。",
        "planned_focus": "我准备重点写prompt检查器和格式化模板。",
    }, ensure_ascii=False)

    result = CliRunner().invoke(
        main,
        ["skill", "preview", "--stdin-json", "--json"],
        input=stdin_payload,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["risk_level"] == "high"
    assert payload["missing_before_start"]


def test_phase12_preview_decomposes_visual_boundaries_and_literalization():
    preview = preview_attention(
        "小男孩拿着手机打游戏，重点是小男孩的沉浸感。",
        "我准备画一个小男孩拿着手机，手机屏幕上显示游戏画面。",
    )

    payload = preview.to_dict()
    boundary = payload["boundary_decomposition"]
    assert boundary is not None
    assert any(
        item["element"] == "手机"
        for item in boundary["must_show"]
    )
    shown = {
        item["element"]
        for group in boundary.values()
        for item in group
    }
    assert "点是小" not in shown
    assert "拿着手" not in shown
    assert "小男孩" in shown
    assert "打游戏" in shown
    assert payload["literalization_risks"]
    assert any(
        risk["element"] == "打游戏"
        for risk in payload["literalization_risks"]
    )
    assert payload["boundary_questions"]
    question = payload["boundary_questions"][0]
    assert "你是否真的想看到打游戏的画面" in question["question"]
    assert [option["label"] for option in question["options"]] == [
        "A", "B", "C"
    ]
    assert any(option["recommended"] for option in question["options"])
    # `重点是小男孩的沉浸感` 是真正的 must，plan 完全没覆盖 `沉浸感`，
    # 因此优先级更高的 rewrite_planned_focus 应当先于 boundary_question 触发；
    # 边界反问不会丢，仍在 boundary_questions / next_steps 里。
    assert payload["activation_decision"]["action"] == "rewrite_planned_focus"
    assert payload["activation_decision"]["should_stop"] is True
    assert any(
        "打游戏" in step for step in payload["activation_decision"]["next_steps"]
    )


def test_phase12_preview_splits_mixed_positive_and_negative_clauses():
    preview = preview_attention(
        "小男孩拿着手机打游戏，重点是沉浸感，不要出现游戏UI。",
        "我准备画小男孩拿手机，屏幕上显示游戏UI。",
    )

    boundary = preview.to_dict()["boundary_decomposition"]
    must_show = {item["element"] for item in boundary["must_show"]}
    can_imply = {item["element"] for item in boundary["can_imply"]}
    must_not_show = {item["element"] for item in boundary["must_not_show"]}

    assert "小男孩" in must_show
    assert "手机" in must_show
    assert "沉浸感" in can_imply
    assert "打游戏" in can_imply
    assert "游戏UI" in must_not_show
    assert "小男孩" not in must_not_show
    assert "手机" not in must_not_show
    assert "沉浸感" not in must_not_show


def test_phase12_skill_preview_cli_json_includes_boundary_fields():
    result = CliRunner().invoke(main, [
        "skill",
        "preview",
        "--context-text",
        "小男孩拿着手机打游戏，重点是小男孩的沉浸感。",
        "--plan-text",
        "我准备画一个小男孩拿着手机，手机屏幕上显示游戏画面。",
        "--json",
    ])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["boundary_decomposition"] is not None
    assert payload["literalization_risks"]
    assert payload["boundary_questions"]


def test_phase13_preview_detects_context_contamination_from_old_focus():
    preview = preview_attention(
        "先整理README和发布说明。现在改成视觉生成："
        "小男孩拿着手机打游戏，重点是小男孩的沉浸感。",
        "我准备继续整理README结构和发布说明。",
    )

    payload = preview.to_dict()
    risks = payload["context_contamination_risks"]
    assert preview.risk_level == "high"
    assert preview.should_continue is False
    assert risks
    assert risks[0]["severity"] == "high"
    assert "readme" in risks[0]["contaminant"]
    assert "小男孩" in risks[0]["active_context"]
    assert any("切断旧上下文污染" in line for line in payload["opening_patch"])
    assert payload["activation_decision"]["action"] == "cut_context_contamination"
    assert payload["activation_decision"]["should_stop"] is True


def test_phase13_skill_preview_cli_json_includes_context_contamination():
    result = CliRunner().invoke(main, [
        "skill",
        "preview",
        "--context-text",
        "先整理README和发布说明。现在改成视觉生成："
        "小男孩拿着手机打游戏，重点是小男孩的沉浸感。",
        "--plan-text",
        "我准备继续整理README结构和发布说明。",
        "--json",
    ])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["risk_level"] == "high"
    assert payload["context_contamination_risks"]


def test_phase14_skill_preview_default_hides_technical_maps():
    result = CliRunner().invoke(main, [
        "skill",
        "preview",
        "--context-text",
        "小男孩拿着手机打游戏，重点是小男孩的沉浸感。",
        "--plan-text",
        "我准备画一个小男孩拿着手机，手机屏幕上显示游戏画面。",
    ])

    assert result.exit_code == 0, result.output
    assert "Boundary Contract" in result.output
    assert "Activation Decision" in result.output
    assert "Boundary Questions" in result.output
    assert "Opening Patch" in result.output
    assert "User Intent Map" not in result.output
    assert "Planned Attention Map" not in result.output
    assert "Missing Before Start" not in result.output
    assert "Control Levers" not in result.output


def test_phase14_skill_preview_debug_shows_technical_maps():
    result = CliRunner().invoke(main, [
        "skill",
        "preview",
        "--context-text",
        "小男孩拿着手机打游戏，重点是小男孩的沉浸感。",
        "--plan-text",
        "我准备画一个小男孩拿着手机，手机屏幕上显示游戏画面。",
        "--debug",
    ])

    assert result.exit_code == 0, result.output
    assert "User Intent Map" in result.output
    assert "Planned Attention Map" in result.output
    assert "Missing Before Start" in result.output
    assert "Control Levers" in result.output
