import json
import sys
import time
from classifier import classify
from test_cases import TEST_CASES
from test_extended import TEST_EXTENDED


def run_suite(cases, label):
    correct = 0
    failures = []
    for case in cases:
        result = classify(case["message"], case["employee"])
        obtained = result.get("tipo", "ERROR")
        expected = case["expected_tipo"]
        ok = obtained == expected
        if ok:
            correct += 1
        else:
            failures.append(case["id"])
        conf = result.get("confianza", "?")
        icon = "✅" if ok else "❌"
        print(f"[{icon}] {case['id']} — esperado: {expected} | obtenido: {obtained} | conf: {conf}")
        if obtained == "ERROR":
            print(f"    JSON: {json.dumps(result, ensure_ascii=False)}")

    pct = correct / len(cases) * 100
    print(f"\n{label}: {correct}/{len(cases)} ({pct:.0f}%)")
    if failures:
        print(f"Fallos: {', '.join(failures)}")
    return correct, len(cases)


def main():
    suite = sys.argv[1] if len(sys.argv) > 1 else "all"

    if suite in ("core", "all"):
        print("=" * 60)
        print("SUITE CORE — 20 casos")
        print("=" * 60)
        c1, t1 = run_suite(TEST_CASES, "Core")

    if suite in ("extended", "all"):
        print("\n" + "=" * 60)
        print("SUITE EXTENDED — 100 casos")
        print("=" * 60)
        c2, t2 = run_suite(TEST_EXTENDED, "Extended")

    if suite == "all":
        total_c = c1 + c2
        total_t = t1 + t2
        print(f"\n{'=' * 60}")
        print(f"TOTAL COMBINADO: {total_c}/{total_t} ({total_c/total_t*100:.0f}%)")


if __name__ == "__main__":
    main()
