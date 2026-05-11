import json
import sys
import time
from classifier import classify
from test_cases import TEST_CASES
from test_extended import TEST_EXTENDED
from test_cross_department import CROSS_TESTS


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


def run_cross_suite(cases, label):
    correct = 0
    failures = []
    for case in cases:
        result = classify(case["message"], case["employee"])
        obtained_tipo = result.get("tipo", "ERROR")
        obtained_cat = result.get("categoria")
        obtained_nota = result.get("tipo_nota_huesped")

        expected_tipo = case["expected_tipo"]
        expected_cat = case.get("expected_categoria")
        expected_nota = case.get("expected_tipo_nota_huesped")

        ok_tipo = obtained_tipo == expected_tipo
        ok_cat = (expected_cat is None) or (obtained_cat == expected_cat)
        ok_nota = (expected_nota is None) or (obtained_nota == expected_nota)
        ok = ok_tipo and ok_cat and ok_nota

        if ok:
            correct += 1
        else:
            failures.append(case["id"])

        conf = result.get("confianza", "?")
        icon = "✅" if ok else "❌"
        detail = f"tipo={obtained_tipo}, cat={obtained_cat}"
        if expected_nota:
            detail += f", nota={obtained_nota}"
        print(f"[{icon}] {case['id']} — {detail} | conf: {conf}")
        if not ok_tipo:
            print(f"    tipo esperado: {expected_tipo}")
        if not ok_cat:
            print(f"    categoria esperada: {expected_cat} | obtenida: {obtained_cat}")
        if not ok_nota:
            print(f"    tipo_nota esperado: {expected_nota} | obtenido: {obtained_nota}")
        if obtained_tipo == "ERROR":
            print(f"    JSON: {json.dumps(result, ensure_ascii=False)}")

    pct = correct / len(cases) * 100
    print(f"\n{label}: {correct}/{len(cases)} ({pct:.0f}%)")
    if failures:
        print(f"Fallos: {', '.join(failures)}")
    return correct, len(cases)


def main():
    suite = sys.argv[1] if len(sys.argv) > 1 else "all"

    c1, t1, c2, t2, c3, t3 = 0, 0, 0, 0, 0, 0

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

    if suite in ("cross", "all"):
        print("\n" + "=" * 60)
        print("SUITE CROSS-DEPARTMENT — 5 casos")
        print("=" * 60)
        c3, t3 = run_cross_suite(CROSS_TESTS, "Cross")

    if suite == "all":
        total_c = c1 + c2 + c3
        total_t = t1 + t2 + t3
        print(f"\n{'=' * 60}")
        print(f"TOTAL COMBINADO: {total_c}/{total_t} ({total_c/total_t*100:.0f}%)")


if __name__ == "__main__":
    main()
