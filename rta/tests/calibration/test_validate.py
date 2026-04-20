from poker_rta.calibration.validate import validate_step


def test_validate_step_pass() -> None:
    row = validate_step(
        step_index=0,
        description="all match",
        expected={"x": 1, "y": "hello"},
        observed={"x": 1, "y": "hello"},
    )
    assert row.passed is True
    assert row.mismatches == []
    assert row.step_index == 0
    assert row.description == "all match"


def test_validate_step_single_mismatch() -> None:
    row = validate_step(
        step_index=2,
        description="one differs",
        expected={"x": 42, "y": "ok"},
        observed={"x": 99, "y": "ok"},
    )
    assert row.passed is False
    assert len(row.mismatches) == 1
    assert "42" in row.mismatches[0]
    assert "99" in row.mismatches[0]
