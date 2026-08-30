from xiumi_layout_agent.chat.workflow import Stage, WorkflowError, WorkflowState


def test_normal_flow():
    ws = WorkflowState()
    assert ws.stage is Stage.IDLE
    for target in [Stage.COLLECT_TEMPLATE, Stage.COLLECT_DRAFT,
                   Stage.CONFIRM_LEVELS, Stage.REPLACE, Stage.DELIVERED]:
        ws.advance(target)
    assert ws.stage is Stage.DELIVERED


def test_illegal_jump_rejected():
    ws = WorkflowState()
    try:
        ws.advance(Stage.REPLACE)
    except WorkflowError as e:
        assert "还不能跳" in str(e)
    else:
        raise AssertionError("should reject IDLE->REPLACE")


def test_delivered_can_reopen():
    ws = WorkflowState()
    for target in [Stage.COLLECT_TEMPLATE, Stage.COLLECT_DRAFT,
                   Stage.CONFIRM_LEVELS, Stage.REPLACE, Stage.DELIVERED]:
        ws.advance(target)
    assert ws.can_go(Stage.IDLE)
    ws.advance(Stage.IDLE)
    assert ws.stage is Stage.IDLE
    assert len(ws.history) == 6
