from pathlib import Path
from brain import process_message
from audio_test_cases import AUDIO_TEST_CASES

AUDIOS_DIR = Path(__file__).parent / "audios"
MARIA = {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"}
ANDREI = {"nombre": "Andrei", "departamento": "MANTENIMIENTO", "idioma": "ro"}

passed = 0
total = 0


def check(label, result, assertions):
    global passed, total
    total += 1
    failures = []
    for desc, ok in assertions:
        if not ok:
            failures.append(desc)
    meta = result.get("_meta", {})
    if failures:
        print(f"[❌] {label}")
        print(f"   Tipo: {result.get('tipo')} | Meta: {meta}")
        for f in failures:
            print(f"   ✗ {f}")
    else:
        passed += 1
        print(f"[✅] {label}")
        print(f"   Tipo: {result.get('tipo')} | Meta: {meta}")


# ── TEST 1 — Texto en español ─────────────────────────────────────────────────
result = process_message(
    "Hay un goteo en el aire acondicionado de la 204",
    MARIA,
)
meta = result.get("_meta", {})
check("TEST 1 — Texto español (goteo 204)", result, [
    ("tipo == INCIDENCIA", result.get("tipo") == "INCIDENCIA"),
    ("_meta.input_type == text", meta.get("input_type") == "text"),
    ("_meta.transcription is None", meta.get("transcription") is None),
    ("_meta.error is None", meta.get("error") is None),
])

# ── TEST 2 — Audio en español ─────────────────────────────────────────────────
audio_es = AUDIOS_DIR / AUDIO_TEST_CASES[0]["filename"]
if not audio_es.exists():
    print(f"[⏭️ ] TEST 2 — Audio español ({AUDIO_TEST_CASES[0]['filename']}) — archivo no encontrado, salteado")
else:
    result = process_message(str(audio_es), MARIA, is_audio=True)
    meta = result.get("_meta", {})
    check("TEST 2 — Audio español (sauna/spa)", result, [
        ("tipo != ERROR", result.get("tipo") != "ERROR"),
        ("_meta.input_type == audio", meta.get("input_type") == "audio"),
        ("_meta.transcription not None", meta.get("transcription") is not None),
        ("_meta.audio_language_detected == Spanish", meta.get("audio_language_detected") == "Spanish"),
    ])

# ── TEST 3 — Audio en rumano ──────────────────────────────────────────────────
audio_ro = AUDIOS_DIR / AUDIO_TEST_CASES[4]["filename"]
if not audio_ro.exists():
    print(f"[⏭️ ] TEST 3 — Audio rumano ({AUDIO_TEST_CASES[4]['filename']}) — archivo no encontrado, salteado")
else:
    result = process_message(str(audio_ro), ANDREI, is_audio=True, language_hint="ro")
    meta = result.get("_meta", {})
    check("TEST 3 — Audio rumano (descripcion en español)", result, [
        ("tipo != ERROR", result.get("tipo") != "ERROR"),
        ("_meta.audio_language_detected == Romanian", meta.get("audio_language_detected") == "Romanian"),
        ("descripcion not None", result.get("descripcion") is not None),
    ])

# ── TEST 4 — Audio inexistente ────────────────────────────────────────────────
result = process_message("audios/no_existe.flac", MARIA, is_audio=True)
meta = result.get("_meta", {})
check("TEST 4 — Audio inexistente", result, [
    ("tipo == ERROR", result.get("tipo") == "ERROR"),
    ("_meta.error not None", meta.get("error") is not None),
    ("_meta.input_type == audio", meta.get("input_type") == "audio"),
])

# ── TEST 5 — Texto vacío ──────────────────────────────────────────────────────
result = process_message("", MARIA)
meta = result.get("_meta", {})
tipo = result.get("tipo")
check("TEST 5 — Texto vacío", result, [
    ("tipo == ERROR o NO_REPORTE", tipo in ("ERROR", "NO_REPORTE")),
    ("_meta.input_type == text", meta.get("input_type") == "text"),
    ("sin excepción", True),
])

# ── Resumen ───────────────────────────────────────────────────────────────────
print(f"\nTests OK: {passed}/{total}")
