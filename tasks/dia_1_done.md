# Día 1 Sprint 1 — Plan de trabajo

## Decisión técnica pre-código

`google-generativeai` está deprecated desde nov 2025. El paquete correcto es `google-genai` (v1.74.0).
- Nueva API: `genai.Client(api_key=...)` + `client.models.generate_content(...)`
- JSON mode disponible vía `response_mime_type="application/json"` en `GenerateContentConfig`
- No necesito pydantic para el JSON mode, solo el mime type es suficiente

---

## Pasos

- [x] 1. Consultar docs actualizadas de google-genai (PyPI + ejemplo de uso)
- [x] 2. Escribir este plan antes de escribir código
- [x] 3. Crear `requirements.txt` con `google-genai` y `python-dotenv`
- [x] 4. Crear `.env.example` y `.gitignore`
- [x] 5. Crear `tasks/lessons.md`
- [x] 6. Crear `test_cases.py` con los 20 casos exactos de la spec
- [x] 7. Crear `classifier.py`:
  - Constante `SYSTEM_PROMPT`
  - Setup del cliente Gemini desde `.env`
  - Función `classify(message, employee)` con JSON mode
- [x] 8. Crear `evaluate.py` con el loop de evaluación
- [x] 9. Instalar dependencias y verificar que `python evaluate.py` corre
- [x] 10. Revisar accuracy → 19/20 al primer intento. Por encima del umbral, no se itera más.
- [x] 11. Escribir sección "Review" en este archivo

---

## Review

### Qué hice

Construí los tres archivos Python + archivos de config exactamente según la spec. Sin módulos extra, sin clases, sin abstracción del cliente LLM.

### Decisiones no obvias

**1. Cambio de paquete: `google-generativeai` → `google-genai`**
El paquete de la spec está deprecated desde nov 2025. El nuevo es `google-genai` (v1.74.0) con interfaz `genai.Client`. Usé eso.

**2. Cambio de modelo: `gemini-1.5-flash` → `gemini-2.5-flash`**
`gemini-1.5-flash` ya no existe en la API (404). `gemini-2.0-flash` tampoco está disponible para claves nuevas. `gemini-2.5-flash` es el actual modelo gratuito recomendado y funciona.

**3. JSON mode via `response_mime_type="application/json"`**
La API soporta JSON mode nativo — lo usé. Esto elimina prácticamente todos los errores de parseo. Solo conservé el parser de fallback por la regla de la spec.

### Resultado

**Accuracy: 19/20 (95%)**

Único fallo: **OBS-03** — "Las llaves magnéticas se están descargando muy rápido"
- Esperado: `OBSERVACION`
- Obtenido: `INCIDENCIA` (confianza 0.9)
- Análisis: la frontera es genuinamente ambigua. "Descargarse rápido" podría requerir acción concreta (reprogramar o reemplazar las llaves), lo cual encaja en INCIDENCIA. El criterio de la spec es "patrón sin acción inmediata", pero el modelo interpreta que hay una acción implícita. Para corregirlo habría que añadir una regla explícita en el system prompt sobre patrones de equipamiento vs fallos puntuales. No lo corrijo en Día 1 per instrucciones de la spec.

### Pendiente para días siguientes

- Día 3: abstraer cliente LLM
- Futuro: afinar campos secundarios (prioridad, categoría) en casos concretos
- Futuro: añadir regla al prompt para OBS-03 si el patrón se repite

---

## Criterio de éxito verificable

`python evaluate.py` imprime `Accuracy: N/20` con N >= 17.
