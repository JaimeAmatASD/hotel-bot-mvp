import unicodedata
from pathlib import Path
from audio_test_cases import AUDIO_TEST_CASES
from transcriber import transcribe

AUDIOS_DIR = Path(__file__).parent / "audios"


def _normalize(text: str) -> str:
    text = text.lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def main():
    processed = 0
    correct = 0

    for case in AUDIO_TEST_CASES:
        audio_path = AUDIOS_DIR / case["filename"]

        if not audio_path.exists():
            print(f"[⏭️ ] {case['id']} — archivo no encontrado, salteado")
            continue

        result = transcribe(str(audio_path), language=case["language"])
        processed += 1

        duration = result.get("duration_seconds") or 0
        detected_lang = result.get("language") or "?"
        text = result.get("text", "")
        error = result.get("error")

        if error:
            print(f"[❌] {case['id']} | error: {error}")
            print(f"     Descripción: {case['description']}")
            continue

        print(f"\n[{'✅' if True else '❌'}] {case['id']} | idioma detectado: {detected_lang} | duración: {duration:.1f}s")
        print(f"   Texto: \"{text}\"")

        normalized_text = _normalize(text)
        missing = [kw for kw in case["expected_keywords"] if _normalize(kw) not in normalized_text]

        if not missing:
            print(f"   Keywords: ✅ todas presentes {case['expected_keywords']}")
            correct += 1
        else:
            print(f"   Keywords: ❌ faltaron {missing} de {case['expected_keywords']}")

    print(f"\nAudios procesados: {correct}/{processed} correctos.")
    if processed < len(AUDIO_TEST_CASES):
        skipped = len(AUDIO_TEST_CASES) - processed
        print(f"({skipped} salteados — archivos no encontrados en audios/)")


if __name__ == "__main__":
    main()
