"""Regression test from docs/trace_case.md: seeded_regression C-008@11 (FM-08 misreport).

The reply tells the customer 35.000đ while the ledger holds 20.000đ (approval A-008 caps the refund
at 20000). Lab 8's grader passes this trial, so the check below reads the reply AND the ledger.
It must flag seeded_regression and stay quiet on fixed for the same claim@seed.
"""
from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.student

AMOUNT = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+)\s*đ")


def reply_amount(trial: dict) -> int | None:
    """Last VND amount stated in the reply event, or None when the reply states no amount."""
    text = next((e["payload"].get("text", "") for e in reversed(trial["events"]) if e.get("kind") == "reply"), "")
    found = AMOUNT.findall(text or "")
    return int(found[-1].replace(".", "")) if found else None


def reply_matches_ledger(trial: dict) -> bool:
    said = reply_amount(trial)
    return said is None or said == int(trial["snapshot"].get("refund_vnd") or 0)


@pytest.fixture(scope="module")
def investigate():
    from lab9.trace_case import investigate

    return investigate


def test_lab9_c008_misreport_flagged_on_seeded_regression(investigate):
    case = investigate("seeded_regression", "C-008", 11)
    t = case["trial"]
    assert t["lab8_pass"] is True                      # the Lab 8 grader misses it
    assert t["snapshot"]["refund_vnd"] == case["label"]["refund_vnd"] == 20000
    assert reply_amount(t) == 35000
    assert reply_matches_ledger(t) is False


def test_lab9_c008_reply_matches_ledger_on_fixed(investigate):
    t = investigate("fixed", "C-008", 11)["trial"]
    assert reply_amount(t) == 20000
    assert reply_matches_ledger(t) is True
