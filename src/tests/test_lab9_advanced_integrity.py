"""M7 regression tests for traps beyond the public ones (duplicates, crashed grader on a green run,
hand-edited metrics, slice relabel, ratchet escape by version bump). Synthetic reports, no shape run."""
import copy

import pytest

pytestmark = pytest.mark.student

ROWS = [{"item_id": f"E-{i:03d}", "seed": s, "pass_rate": i != 3 or s != 2, "cost": 1.0,
         "slices": ["money_movement"] if i < 2 else []}
        for i in range(4) for s in (1, 2)]
SPEC = {"eval_set_version": "v2", "metrics": [{"id": "pass_rate", "kind": "capability", "blocking": True,
                                               "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.9, "blocking": True}]}


def report(rows=None, **metrics):
    rows = copy.deepcopy(ROWS if rows is None else rows)
    return {"manifest": {"eval_set_sha": "x", "items": 4, "seeds": [1, 2]}, "rows": rows,
            "metrics": {"pass_rate": 0.875, **metrics}, "evaluator_failures": []}


@pytest.fixture(scope="module")
def gate():
    from lab9 import gate

    return gate


def test_advanced_honest_report_is_clean(gate):
    assert gate.integrity_check(report(), report(), SPEC, SPEC) == []


def test_advanced_duplicate_row_swap_is_flagged(gate):
    rows = copy.deepcopy(ROWS)
    rows[-1] = copy.deepcopy(rows[0])          # failing row replaced by a copy of a passing one
    assert any("duplicated" in p for p in gate.integrity_check(report(rows, pass_rate=1.0), report(), SPEC))


def test_advanced_evaluator_failures_on_green_run_is_flagged(gate):
    green = report()
    green["evaluator_failures"] = ["E-001@1:Grader:boom"]
    assert gate.integrity_check(green, report(), SPEC)


def test_advanced_hand_edited_metric_is_flagged(gate):
    assert gate.integrity_check(report(pass_rate=1.0), report(), SPEC)


def test_advanced_slice_relabel_is_flagged(gate):
    rows = copy.deepcopy(ROWS)
    for r in rows:
        r["slices"] = []
    assert gate.integrity_check(report(rows), report(), SPEC)


def test_advanced_ratchet_blocks_version_bump_and_unblocking(gate):
    bumped = copy.deepcopy(SPEC)
    bumped["eval_set_version"] = "v3"
    assert gate.integrity_check(report(), report(), bumped, SPEC)
    unblocked = copy.deepcopy(SPEC)
    unblocked["metrics"][0]["blocking"] = False
    assert gate.integrity_check(report(), report(), unblocked, SPEC)
    no_slice = copy.deepcopy(SPEC)
    no_slice["slices"] = []
    assert gate.integrity_check(report(), report(), no_slice, SPEC)
