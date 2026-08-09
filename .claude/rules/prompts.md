---
paths:
  - "classifier.py"
  - "brain.py"
  - "transcriber.py"
---

# Prompts y llamadas al modelo

- **El prompt vive como constante de módulo** (`SYSTEM_PROMPT` en `classifier.py`), no
  incrustado en un f-string en medio de la lógica: así se puede leer, versionar e iterar.
- **Un cambio de prompt es un cambio de comportamiento**, no un retoque de texto. Se
  prueba contra los mismos casos antes y después (`test_cases.py`, `test_extended.py`,
  `test_cross_department.py` vía `evaluate.py`), y si cambió el criterio se anota en
  `decisions.md`.
- **Toda respuesta del modelo se valida antes de usarse.** Se espera JSON: se parsea y
  se valida. Nunca asumas que vino bien formado.
- **El metadato del empleado no es señal de clasificación.** Pasar "departamento" con
  instrucción ambigua hace que el modelo asigne la categoría por quién reporta y no por
  lo que dice el mensaje. Ver L-05 en `tasks/lessons.md`.
- **Nada de texto de usuarios en los logs.** ID y metadata, no el mensaje.
- El texto del empleado nunca se concatena donde pueda leerse como instrucción: va en su
  propio bloque, marcado como contenido.
- Si el modelo falla o tarda, tiene que haber respuesta para el empleado. Nunca colgado
  y sin mensaje.
