---
paths:
  - "tests/**"
  - "**/test_*.py"
---

# Convenciones de tests

- **La suite por defecto no gasta tokens ni toca la red.** `pytest.ini` tiene
  `addopts = -m "not integration"`, y eso es lo que la mantiene barata.
  `tests/integration/` **sí** llama a Gemini y Groq de verdad, a propósito, y se corre
  a mano con `venv/bin/pytest -q -o addopts=''`.
  La prohibición es doble: no saques ese marcador, y no metas llamadas reales a una API
  en un test que corra en la suite por defecto.
- **Rojo antes que verde.** Un test nuevo se ve fallar primero. Si pasa a la primera,
  sospechá que no está probando nada.
- **Un test por bug.** Todo bug arreglado deja el test que lo reproduce, con el nombre
  del síntoma que vio Jaime, no del método interno.
- **Si un test falla, se arregla el código.** Cambiar el assert, subir un umbral o
  marcar `skip` está prohibido salvo que Jaime lo pida explícitamente.
- Sobre salidas generadas se afirma la **forma** (que haya respuesta, que respete el
  formato, que no filtre datos), no el texto exacto del modelo.
- Nombres en idioma del dominio: `test_reporte_trae_el_dia_aunque_ya_este_consolidado`,
  no `test_case_3`.
- Los tests inicializan la base tras `patch.object(storage, "DB_PATH", ...)`. Nunca
  contra `data/hotel_bot.db`.
- **Nada de IDs reales de Telegram en los tests.** Los verdaderos viven solo en
  `config/employees.local.json`, que está gitignoreado. En tests van ficticios.
