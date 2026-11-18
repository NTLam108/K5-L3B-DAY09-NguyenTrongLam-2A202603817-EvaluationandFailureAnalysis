"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


import math
from lab9.eval import aggregate          # dùng lại đúng hàm tổng hợp của harness

def _key(r):
    return (r.get("item_id"), r.get("seed"))

def integrity_check(pr, base, spec, base_spec=None):
    problems: list[str] = []
    rows, brows = pr.get("rows") or [], base.get("rows") or []

    # 1. NaN / inf trong metrics
    for m, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            problems.append(f"metric {m} is {v}")

    # 2. Số dòng khớp manifest, không trùng lặp
    man = pr.get("manifest") or {}
    want = int(man.get("items") or 0) * len(man.get("seeds") or [])
    if len(rows) != want:
        problems.append(f"{len(rows)} rows, manifest says {want}")
    keys = [_key(r) for r in rows]
    if len(keys) != len(set(keys)):
        problems.append("duplicated (item, seed) rows")

    # 3. Cùng tập (item, seed) và cùng manifest với baseline
    if set(keys) != {_key(r) for r in brows}:
        problems.append("(item, seed) set differs from baseline (dropped / cherry-picked)")
    for f in ("items", "seeds"):
        if man.get(f) != (base.get("manifest") or {}).get(f):
            problems.append(f"manifest.{f} differs from baseline")

    # 4. Grader hỏng: evaluator_failures, hoặc ô None ở metric được chấm
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator failure(s)")
    graded = [m["id"] for m in spec["metrics"] if any(m["id"] in r for r in brows + rows)]
    for r in rows:
        bad = [m for m in graded if r.get(m) is None]
        if bad:
            problems.append(f"{_key(r)} has no value for {bad}"); break

    # 5. Metric khai báo phải khớp với metric tính lại từ rows (bắt sửa tay report)
    if rows:
        ids = [m for m in graded if all(m in r for r in rows)]
        # aggregate() needs a cost column for cost_per_success, which is not compared here;
        # default it so a report without cost (e.g. a trimmed report) does not crash the check.
        again = aggregate([{**r, "cost": r.get("cost") or 0.0} for r in rows], ids,
                          k_values=spec.get("pass_k", []))
        for m in ids + ["pass_5"] + [f"pass_hat_{k}" for k in spec.get("pass_k", [])]:
            a, b = pr["metrics"].get(m), again.get(m)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) > 1e-6:
                problems.append(f"metric {m}={a} but rows give {b}")

    # 6. Slice tag của từng item phải giống baseline
    btags = {r["item_id"]: sorted(r.get("slices") or []) for r in brows}
    for r in rows:
        if r["item_id"] in btags and sorted(r.get("slices") or []) != btags[r["item_id"]]:
            problems.append(f"{r['item_id']} slice tags changed"); break

    # 7. Ratchet
    if base_spec is not None:
        problems += _ratchet(spec, base_spec, pr, base)
    return problems

def _ratchet(spec, base_spec, pr, base):
    out = []
    same_version = spec.get("eval_set_version") == base_spec.get("eval_set_version")
    if not same_version and pr["manifest"]["eval_set_sha"] == base["manifest"]["eval_set_sha"]:
        out.append("spec claims a new eval_set_version but the eval set is unchanged")
    if not same_version:
        return out                               # version mới thì được đặt lại ngưỡng
    def check(tag, old, new):
        if new is None:
            out.append(f"{tag} removed"); return
        if old.get("blocking") and not new.get("blocking"):
            out.append(f"{tag} no longer blocking")
        ot, nt = old.get("threshold", old), new.get("threshold", new)   # slice để ngưỡng phẳng
        if "min" in ot and ("min" not in nt or nt["min"] < ot["min"]):
            out.append(f"{tag} min lowered")
        if "max" in ot and ("max" not in nt or nt["max"] > ot["max"]):
            out.append(f"{tag} max raised")
        if "max_increase" in ot and ("max_increase" not in nt or nt["max_increase"] > ot["max_increase"]):
            out.append(f"{tag} max_increase raised")
        if ot.get("no_significant_drop") and not nt.get("no_significant_drop"):
            out.append(f"{tag} dropped no_significant_drop")
    new_m = {m["id"]: m for m in spec["metrics"]}
    for m in base_spec["metrics"]:
        check(f"metric {m['id']}", m, new_m.get(m["id"]))
    new_s = {(s["name"], s["metric"]): s for s in spec.get("slices") or []}
    for s in base_spec.get("slices") or []:
        check(f"slice {s['name']}/{s['metric']}", s, new_s.get((s["name"], s["metric"])))
    return out


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, metric = s["name"], s["metric"]
        sid = f"slice:{name}/{metric}"
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        val, note, verdict = None, "", "ok"
        if not a:
            # A slice no PR row carries cannot vouch for anything: relabelled items or a dropped
            # metric would otherwise make the slice gate silently pass.
            verdict, note = "missing", "no PR item carries this slice"
        else:
            val = round(sum(a.values()) / len(a), 4)
            if "min" in s and val < s["min"]:
                verdict = "fail"
            keys = sorted(set(a) & set(b))
            if s.get("no_significant_drop") and keys:
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000),
                                                   rng=bs.get("rng", 2027))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        th = {k: s[k] for k in ("min", "no_significant_drop") if k in s}
        lines.append(f"  {sid:<38} {val!s:<8} n={len(a):<3} {json.dumps(th):<34} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
