import pytest

from stateprobe.mcp_server import overlay_attention, preview_attention_tool


def test_overlay_attention_returns_structured_hud():
    hud = overlay_attention(
        context="核心是让agent的注意力可见。不要把格式化当主线。",
        output="StateProbe是一个prompt检查器，格式化模板是核心。",
    )

    assert hud["drift_level"] in {"medium", "high"}
    assert hud["interrupt_level"] in {"watch", "interrupt"}
    assert "user_intent_map" in hud
    assert "agent_attention_map" in hud
    assert "attention_gaps" in hud
    assert "output_trajectory" in hud
    assert "control_levers" in hud
    assert isinstance(hud["control_levers"], dict)


@pytest.mark.parametrize(
    ("context", "output", "expected"),
    [
        ("", "agent output", "context must be a non-empty string"),
        ("user context", "", "output must be a non-empty string"),
        (None, "agent output", "context must be a non-empty string"),
        ("user context", None, "output must be a non-empty string"),
    ],
)
def test_overlay_attention_rejects_empty_inputs(context, output, expected):
    with pytest.raises(ValueError, match=expected):
        overlay_attention(context=context, output=output)


def test_preview_attention_tool_returns_opening_preview():
    preview = preview_attention_tool(
        context="核心是让agent的注意力可见。不要把格式化当主线。",
        planned_focus="我准备重点写prompt检查器和格式化模板。",
    )

    assert preview["risk_level"] == "high"
    assert preview["should_continue"] is False
    assert preview["user_intent_map"]
    assert preview["planned_attention_map"]
    assert preview["missing_before_start"]
    assert preview["control_levers"]["boost"]
    assert preview["activation_decision"]["action"] == "rewrite_planned_focus"
    assert preview["activation_decision"]["should_stop"] is True


def test_preview_attention_tool_returns_visual_boundary_contract():
    preview = preview_attention_tool(
        context="小男孩拿着手机打游戏，重点是小男孩的沉浸感。",
        planned_focus="我准备画一个小男孩拿着手机，手机屏幕上显示游戏画面。",
    )

    boundary = preview["boundary_decomposition"]
    assert boundary["must_show"]
    assert boundary["can_imply"]
    assert any(item["element"] == "手机" for item in boundary["must_show"])
    assert any(item["element"] == "打游戏" for item in boundary["can_imply"])
    assert any(
        risk["element"] == "打游戏"
        for risk in preview["literalization_risks"]
    )
    assert preview["boundary_questions"]
    assert [option["label"] for option in preview["boundary_questions"][0]["options"]] == [
        "A",
        "B",
        "C",
    ]
    assert preview["activation_decision"]["action"] == "ask_boundary_question"
    assert preview["activation_decision"]["should_stop"] is True


def test_preview_attention_tool_returns_context_contamination_risks():
    preview = preview_attention_tool(
        context=(
            "先整理README和发布说明。现在改成视觉生成："
            "小男孩拿着手机打游戏，重点是小男孩的沉浸感。"
        ),
        planned_focus="我准备继续整理README结构和发布说明。",
    )

    risks = preview["context_contamination_risks"]
    assert risks
    assert risks[0]["severity"] == "high"
    assert "readme" in risks[0]["contaminant"]
    assert preview["should_continue"] is False
    assert preview["activation_decision"]["action"] == "cut_context_contamination"
    assert preview["activation_decision"]["should_stop"] is True


@pytest.mark.parametrize(
    ("context", "planned_focus", "expected"),
    [
        ("", "planned focus", "context must be a non-empty string"),
        ("user context", "", "planned_focus must be a non-empty string"),
        (None, "planned focus", "context must be a non-empty string"),
        ("user context", None, "planned_focus must be a non-empty string"),
    ],
)
def test_preview_attention_tool_rejects_empty_inputs(
    context, planned_focus, expected
):
    with pytest.raises(ValueError, match=expected):
        preview_attention_tool(
            context=context,
            planned_focus=planned_focus,
        )
