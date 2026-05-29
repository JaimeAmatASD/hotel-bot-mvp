# hotel-bot-mvp

Clasificador de mensajes operativos de hotel vía Telegram. Convierte texto y audio de empleados en JSON estructurado (INCIDENCIA / OBSERVACION / GUEST_INTEL / NO_REPORTE).

## Stack

- Clasificador: Gemini 2.5 Flash (Google AI Studio, gratuito)
- Transcriptor: Whisper Large v3 Turbo (Groq, gratuito)
- Dashboard: Streamlit

## Tests

```bash
# Suite normal sin llamadas reales a APIs externas
venv/bin/pytest -q

# Suite completa, incluyendo integration tests Gemini/Groq
venv/bin/pytest -q -o addopts=''

# Protocolo hotelero automatizado (empleado, encargado, gerente)
venv/bin/pytest -q tests/test_hotel_scenarios.py
```

## Uso del cerebro desde otro módulo

```python
from brain import process_message

# Texto:
result = process_message(
    "Hay un goteo en el aire acondicionado de la 204",
    {"nombre": "María", "departamento": "HOUSEKEEPING", "idioma": "es"}
)

# Audio:
result = process_message(
    "/ruta/al/audio.ogg",
    {"nombre": "Andrei", "departamento": "MANTENIMIENTO", "idioma": "ro"},
    is_audio=True
)

print(result["tipo"], result["descripcion"])
# INCIDENCIA  Goteo en aire acondicionado habitación 204
```
