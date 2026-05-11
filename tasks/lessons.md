# Lessons learned

## L-01: Verificar nombre del modelo antes de usarlo

`google-generativeai` está deprecated. El paquete actual es `google-genai`.
Los modelos `gemini-1.5-flash` y `gemini-2.0-flash` ya no están disponibles para claves nuevas.
Usar `gemini-2.5-flash` (o listar modelos con `client.models.list()` para confirmar disponibilidad).

## L-02: Usar nombre exacto del paquete PyPI para el SDK de Gemini

La spec decía `google-generativeai` pero ese paquete está deprecated desde nov 2025.
Siempre verificar PyPI antes de usar el nombre del paquete en requirements.txt.

## L-03: context.user_data en python-telegram-bot persiste por usuario entre mensajes

`context.user_data` es un dict que el framework mantiene en memoria por cada chat_id.
No requiere init explícito — acceder con `.get()` siempre es seguro.
Para estado de corrección: guardar `awaiting_correction`, `correction_started_at` y `pending`
como tres claves separadas facilita el cleanup atómico con `pop()` sin KeyError.

## L-06: Estados de espera separados vs unificados en bots conversacionales

Cuando hay dos tipos de "esperar respuesta del usuario" (corrección iniciada por el usuario,
followup iniciado por el bot), mantenerlos como flags separadas (`awaiting_correction`,
`awaiting_followup`) es mejor que fusionarlos si uno ya funciona y está testeado.
Fusionar requiere refactorizar código estable. La prioridad en el handler es: followup primero
(el bot hizo una pregunta concreta), correction después (el usuario pidió corregir).

## L-07: Detectar ubicaciones genéricas sin número de habitación

El clasificador puede devolver `ubicacion: "Habitación"` o `"una habitación"` sin número.
La señal para detectarlo: `not re.search(r'\d', ubicacion)` + match con palabras conocidas
(habitación, baño, pasillo, etc.). Si se detecta, agregar "ubicacion" a `campos_faltantes`
antes de evaluar si hay campo crítico. Así el mecanismo de followup lo captura automáticamente.

## L-05: Metadato del empleado ≠ contenido del mensaje en prompts de clasificación

Pasar "departamento" del empleado como contexto con instrucción ambigua ("úsalo para entender el contexto")
hace que el modelo lo use como señal de categoría. Un empleado del Spa que reporta una bombilla
fundida tiende a recibir categoría SPA en lugar de MANTENIMIENTO.
Solución: instrucción explícita de que el departamento solo sirve para interpretar lenguaje/jerga,
y que la categoría se asigna EXCLUSIVAMENTE por el contenido del mensaje.
Aplicable a cualquier campo de metadato que pueda confundirse con señal de clasificación.

## L-04: pytest-asyncio requiere marca explícita en modo STRICT

Con `asyncio_mode = strict` (default en pytest-asyncio >= 0.21), los tests async
necesitan el decorador `@pytest.mark.asyncio`. Sin él los tests se saltan silenciosamente.
Agregar `pytest.ini` o `pyproject.toml` con `asyncio_mode = auto` para evitarlo,
o marcar cada test individualmente.
