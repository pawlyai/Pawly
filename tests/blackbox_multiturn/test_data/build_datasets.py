"""
Build canonical test_data/*_cases.json files from gen_*.py outputs.

Each gen_*.py writes <topic>.json. The test loader expects <topic>_cases.json.
This script (a) invokes every gen_*.py to refresh outputs, (b) copies each
<topic>.json -> <topic>_cases.json, and (c) concatenates all per-topic JSONs
into multiturn_pawly_regression_test_all_223_cases.json.

Run from anywhere:
    python3 tests/blackbox_multiturn/test_data/build_datasets.py
"""
import json
import pathlib
import runpy
import shutil
import sys

HERE = pathlib.Path(__file__).parent

GENERATORS: list[tuple[str, str]] = [
    # (gen script, topic basename — output is <topic>.json next to the script)
    ("gen_longitudinal.py", "multiturn_pawly_regression_test_longitudinal"),
    ("gen_p0_compliance.py", "multiturn_pawly_regression_test_p0_compliance"),
    ("gen_p0_dangerous.py", "multiturn_pawly_regression_test_p0_dangerous"),
    ("gen_p0_injection.py", "multiturn_pawly_regression_test_p0_injection"),
    ("gen_p0_outofscope.py", "multiturn_pawly_regression_test_p0_outofscope"),
    ("gen_p1_edge.py", "multiturn_pawly_regression_test_p1_edge"),
    ("gen_p1_emotional.py", "multiturn_pawly_regression_test_p1_emotional"),
    ("gen_p1_general.py", "multiturn_pawly_regression_test_p1_general"),
]

ALL_TOPIC = "multiturn_pawly_regression_test_all_223"


def main() -> int:
    print(f"[build] working dir: {HERE}")
    combined: list[dict] = []

    for script, topic in GENERATORS:
        gen_path = HERE / script
        out_path = HERE / f"{topic}.json"
        cases_path = HERE / f"{topic}_cases.json"

        print(f"\n[build] running {script}")
        # Use runpy so __file__ in the gen script resolves to its real path,
        # which is how it computes its OUT location.
        runpy.run_path(str(gen_path), run_name="__main__")

        if not out_path.exists():
            print(f"  ERROR: {out_path} not produced by {script}", file=sys.stderr)
            return 1

        # Mirror to <topic>_cases.json (what the test loader reads).
        shutil.copyfile(out_path, cases_path)
        print(f"  copied -> {cases_path.name}")

        # Accumulate for the combined dataset.
        with out_path.open("r", encoding="utf-8") as handle:
            combined.extend(json.load(handle))

    total = len(combined)
    print(f"\n[build] combined dataset: {total} cases")

    # The historical name is "all_223" — keep the suffix even if the count drifts;
    # the file is the canonical merged dataset regardless of exact count.
    all_path = HERE / f"{ALL_TOPIC}.json"
    all_cases_path = HERE / f"{ALL_TOPIC}_cases.json"
    payload = json.dumps(combined, indent=2, ensure_ascii=False)
    all_path.write_text(payload, encoding="utf-8")
    all_cases_path.write_text(payload, encoding="utf-8")
    print(f"[build] wrote {all_path.name} and {all_cases_path.name}")

    if total != 223:
        print(f"  NOTE: total cases is {total}, not 223 — verify gen scripts are current")

    return 0


if __name__ == "__main__":
    sys.exit(main())
