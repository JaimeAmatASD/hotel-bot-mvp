# Lessons learned

## L-01: Verificar nombre del modelo antes de usarlo

`google-generativeai` está deprecated. El paquete actual es `google-genai`.
Los modelos `gemini-1.5-flash` y `gemini-2.0-flash` ya no están disponibles para claves nuevas.
Usar `gemini-2.5-flash` (o listar modelos con `client.models.list()` para confirmar disponibilidad).

## L-02: Usar nombre exacto del paquete PyPI para el SDK de Gemini

La spec decía `google-generativeai` pero ese paquete está deprecated desde nov 2025.
Siempre verificar PyPI antes de usar el nombre del paquete en requirements.txt.
