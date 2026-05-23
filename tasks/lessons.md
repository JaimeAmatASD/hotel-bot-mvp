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

## L-04: pytest-asyncio — instalar, fijar en requirements.txt, y configurar asyncio_mode

`pytest-asyncio` no viene con pytest base. Si no está instalado, los tests async fallan
con "async def functions are not natively supported" (no se saltan — fallan). Esto puede
confundirse con un fallo de lógica cuando en realidad es un fallo de infraestructura de tests.

**Fix completo (los tres pasos son necesarios):**
1. `pip install pytest-asyncio` + agregar `pytest-asyncio>=0.23` a `requirements.txt`
2. Crear `pytest.ini` con `asyncio_mode = auto` — sin esto, cada test async necesita
   `@pytest.mark.asyncio` explícito y en modo STRICT se saltan silenciosamente.
3. Verificar que los tests async **corren** (pasan o fallan con lógica), no solo que
   pytest no reporta errores de colección.

**Señal de alerta:** si ves "PytestUnknownMarkWarning: Unknown pytest.mark.asyncio"
en el output de pytest, pytest-asyncio no está instalado o no está en el path correcto.

**Por qué se perdió:** `pytest-asyncio` no estaba en `requirements.txt` desde el inicio
del proyecto. Se instalaba manualmente en el venv durante el desarrollo pero no se
persitía. Al re-crear el venv o en CI, los tests async empezaban a fallar.

## L-08: Estructura de roles — 3 niveles con mapeo categoría→departamento (Sprint B.1)

El bot maneja tres roles: EMPLEADO (reporta), ENCARGADO (actúa en su área), GERENTE_GENERAL (ve todo).
La traducción de categoría de incidencia a departamento responsable vive en `CATEGORY_TO_DEPARTMENT`
en `config/rules.py` — centralizado para que `permissions.py` y futuros módulos lo reutilicen.
Las funciones de permisos reciben el dict de incidencia con el campo `categoria` para hacer el mapeo.

## L-09: permissions.py como módulo aparte — single responsibility

La lógica de "quién puede qué" se separa en `permissions.py` y no en `storage.py` ni `brain.py`
porque tiene un dominio propio (autorización) distinto del almacenamiento (storage) y la IA (brain).
Al estar aislada: se testea sin bot corriendo, se integra gradualmente en los handlers (B.2-B.4),
y no añade acoplamiento a módulos que ya funcionan. Regla: si una función solo pregunta
"¿puede X hacer Y?" pertenece a permissions, no al módulo que ejecuta Y.

## L-10: Backward compat sin migración — .get("rol", "EMPLEADO")

Los empleados registrados antes del Sprint B.1 no tienen campo `rol` en el JSON.
En lugar de migrar el JSON viejo o añadir lógica de normalización en `bot.py`,
la compatibilidad se resuelve en el único punto donde se accede al rol: `permissions.py`.
Patrón: `user.get("rol", "EMPLEADO")` en cada función que necesita el rol.
Ventaja: código de carga (`bot.py`) no sabe nada de este detalle — bajo acoplamiento.

## Sprint B.2 — Notificaciones (2026-05-15)

### Patrón de redirección por entorno (no por usuario)
`NOTIFICATION_REDIRECT_MODE=admin` redirige todas las notificaciones al admin. Es una decisión
de entorno (testing vs producción), no de usuario. El modo se lee en cada `notify_incident()`
desde `config/settings`, por lo que cambiar la variable de entorno y reiniciar el bot es
suficiente para cambiar de modo.

### Filtros por rol — gerente sí, encargado no
Los filtros de notificación (modo, departamentos excluidos) solo aplican a GERENTE_GENERAL.
Los encargados reciben todo lo de su departamento sin filtros. Decisión deliberada: el encargado
necesita ver todo lo de su área para operar; el gerente ajusta la señal/ruido según su estilo.

### La regla "CRITICA siempre llega" como excepción a todos los filtros
Antes de aplicar cualquier filtro (modo, departamentos excluidos), se verifica si
`prioridad == "CRITICA"`. Si es así, el gerente recibe la notificación sin importar nada más.
Implementado como primera condición en `_should_notify_gerente()`. Los filtros controlan
comodidad, no seguridad operacional.

### save() devuelve lastrowid para conectar notificaciones a incidencias
Antes, `save()` retornaba None. Ahora retorna `cur.lastrowid`. Este ID se usa para registrar
en tabla `notifications` qué incidencia disparó qué notificaciones, permitiendo auditoría
posterior en SQLite.

## Sprint B.3 — Botones de acción (2026-05-16)

### callback_data complejo: incluir todo lo necesario en el string

Para callbacks de incidencia: `incident_action:{incident_id}:{sub_action}:{actor_telegram_id}`.
La alternativa (guardar en SQLite + recuperar por incident_id) añade complejidad sin beneficio.
El string resultante (~40 chars) queda bien por debajo del límite de 64 bytes de Telegram.
Regla: mientras el callback_data quepa en 64 bytes, preferir Opción A (todo en el string)
sobre Opción B (tabla auxiliar). Si supera el límite, ahí sí usar tabla.

### Patrón de edición de mensaje original para reflejar cambio de estado

Cuando se pulsa un botón inline, `query.edit_message_text()` edita el mensaje padre.
Para fotos, usar `query.edit_message_caption()` — detectar con `query.message.photo`.
Al reformatear el mensaje, recargar la incidencia desde SQLite con `get_incident(id)`
para obtener los campos actualizados (estado, assigned_at, etc.) y reconstruir el texto.
Evitar pasar el estado como parámetro por separado — el "single source of truth" es la DB.

### query.answer() y show_alert: no llamar antes del handler de incident_action

Si `query.answer()` se llama al inicio del handler para todos los callbacks,
no se puede luego llamar `query.answer(text, show_alert=True)` en ese mismo callback_query_id.
Solución: separar el branch de `incident_action:*` ANTES del `query.answer()` del top.
El branch de acciones maneja su propio `answer()` — con show_alert en fallos, sin texto en éxito.

### Transiciones inválidas: alert vs error silencioso

Las transiciones imposibles (ej: tomar una incidencia ya CERRADA) se responden con
`query.answer(reason, show_alert=True)`. El usuario ve un popup con el motivo y el mensaje
original no se modifica. No se lanza excepción ni se edita el mensaje.
Regla: en handlers de Telegram, errores de lógica de negocio → alert al usuario;
errores de infraestructura (red, DB) → log silencioso y return sin modificar estado.

## Sprint B.5-reportes — Reportes acumulativos de turno (2026-05-20)

### Keyword detection: normalizar antes de comparar
`unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode()` elimina tildes.
Hacer esto tanto al texto del usuario como a los keywords del config, y comparar con `in`
(no `==`) para detectar la keyword dentro de un mensaje más largo.

### Orden de chequeos en los handlers importa
En modo reporte, la verificación de reporte abierto va ANTES de followup/correction.
Si no, un mensaje normal durante modo reporte podría matchear el estado de corrección
pendiente y procesarse incorrectamente. Regla: el estado más específico (reporte abierto)
tiene prioridad sobre el estado más general (followup/correction).

### Audio en modo reporte: solo transcribir, no clasificar
Llamar `transcriber.transcribe(path, language)` directamente en vez de `brain.process_message`.
Esto evita consumir tokens del clasificador para mensajes que quizás no se confirmen.
La clasificación ocurre solo al cerrar el reporte, cuando el empleado ya decidió qué guardar.

### JobQueue en python-telegram-bot v20
`app.job_queue.run_repeating(callback, interval=seconds, first=seconds)`.
El callback recibe `context` con `context.bot` y `context.bot_data`.
El `first` es el delay inicial antes de la primera ejecución — poner 60s para no ejecutar
inmediatamente al arrancar.

### Diseño extensible para timeout
`REPORT_TIMEOUT_HOURS = 12` en `config/settings.py` como constante nombrada.
No hardcodear el valor en el JobQueue ni en la función de expiración.
Post-piloto: leer de tabla de configuración por hotel/empleado.

## Sprint B.5 — Trazabilidad y concurrencia (2026-05-17)

### Patrón de eventos append-only para auditoría

La tabla `incident_events` nunca se modifica ni borra — solo INSERTs.
Esto hace el historial inmutable y confiable. Si algo sale mal en producción,
el log reconstruye exactamente qué pasó y en qué orden.
Regla: un audit log no debe tener UPDATE ni DELETE. Si necesitás "corregir" un evento,
insertá otro con `action="correction"` que referencie al anterior.

### SQLite BEGIN IMMEDIATE para atomic read-modify-write

El patrón correcto en Python sqlite3 para proteger lectura+escritura concurrente:
```python
con = sqlite3.connect(str(DB_PATH))
con.isolation_level = None  # manual transaction control
con.execute("BEGIN IMMEDIATE")  # bloquea para escritura desde el inicio
# lectura y escritura en el mismo bloque
con.execute("COMMIT")
```
`BEGIN IMMEDIATE` bloquea el archivo inmediatamente. Otros escritores esperan.
Lectores sin transacción pueden continuar (WAL mode permite esto).
Importante: usar `isolation_level=None` — sin esto, Python sqlite3 emite BEGIN automático
que interfiere con el BEGIN IMMEDIATE manual.

### extra como TEXT JSON en SQLite

Para datos variables por tipo de evento (destinatario de notificación, redirect_mode, etc.):
`json.dumps(extra or {})` al guardar, `json.loads(row["extra"] or "{}")` al leer.
Simple, sin migraciones, los eventos viejos con `extra=NULL` no rompen nada.
Trade-off: no se puede hacer SELECT por campos dentro del JSON sin `json_extract()`.
Aceptable si los queries sobre `extra` son raros (en este caso lo son).

### test de concurrencia con threading.Barrier

Para testear race conditions sin sleep: `threading.Barrier(2)` sincroniza el arranque
de ambos threads. Ambos llegan a `barrier.wait()`, se bloquean, y arrancan juntos.
Esto maximiza la probabilidad de colisión sin depender de timing.

## Sprint B.5 — Rediseño reportes retrospectivos (2026-05-21)

### Patrón acumulativo retrasa notificaciones — usar procesamiento individual + resumen retrospectivo

El diseño "abrir modo → acumular mensajes → batch al cerrar" parecía ordenado pero
rompía el principio BASE PRIMERO: las incidencias no se notificaban hasta el cierre del turno.
Solución: cada mensaje se procesa individualmente al llegar (flujo A), y el reporte es solo
un resumen retrospectivo de lo ya clasificado. Regla: si una decisión de diseño retrasa
una acción urgente (notificación, alerta), es un error de arquitectura aunque sea "limpia".

### Funciones obsoletas: marcar como DEPRECATED en vez de borrar columnas

Cuando un rediseño elimina un modelo de datos, las tablas viejas (report_messages) y las
columnas relacionadas no se borran de SQLite — requieren migraciones en producción que
pueden romper DBs existentes. Solución: dejar la tabla, quitar las funciones Python que
la escriben, y documentar con "# DEPRECATED" si hay referencias. Rollback sin migración.

### Draft de reporte en user_data, no en DB

El estado "pendiente de confirmación" del reporte vive en `context.user_data` (en memoria),
no en una fila OPEN en la tabla `reports`. Ventaja: si el bot reinicia, no quedan reportes
fantasma en estado OPEN. Contrapartida: el draft se pierde si el bot cae. Aceptable para
este caso porque el empleado puede hacer /reporte de nuevo y reconstruye el resumen.

### callback_data sin ID de recurso cuando el estado vive en user_data

Si los ítems del reporte viven en `user_data`, el callback_data puede ser un string simple
("report_confirm_all", "report_correct") sin necesidad de incluir el report_id ni los IDs
de clasificaciones — el handler lo lee de user_data. Solo incluir IDs en callback_data cuando
no haya otra forma de recuperar el recurso (ej: botones en mensajes de notificación, donde
no hay user_data de contexto).

## Sprint B.4 — Comandos de consulta (2026-05-16)

### unknown_command handler: siempre al final

`MessageHandler(filters.COMMAND, unknown_command)` captura cualquier `/comando` no registrado.
Debe añadirse DESPUÉS de todos los `CommandHandler` específicos, si no, intercepta todo.
También resuelve el bug de UX donde `/spec` o `/config` se ignoraban silenciosamente.

### Filtrado por departamento en Python, no en SQL

`CATEGORY_TO_DEPARTMENT` mapea categoría→departamento en Python (`permissions.py`).
Duplicar ese mapeo en SQL (CASE WHEN ...) crea dos fuentes de verdad que se pueden desincronizar.
Patrón: fetch desde DB con filtros simples (estado, prioridad), luego `filter_visible_incidents()`
+ filtro de departamento en Python. Aceptable para datasets pequeños (<10.000 filas).

### Parsing de argumentos de /abiertas: tipo before valor

Para `/abiertas alta mantenimiento` o `/abiertas mantenimiento alta` en cualquier orden:
detectar el tipo del arg comparando contra un set conocido de prioridades.
Lo que no es prioridad → se trata como departamento. Simple, sin posición fija.
Ventaja: no requiere palabras clave prefijo (dept:, prio:) que complican el UX.

### Tabla de transiciones como dict de bloqueados, no de permitidos

Modelar "qué NO se puede hacer desde este estado" es más mantenible que "qué SÍ se puede",
porque la mayoría de las transiciones son válidas. Solo los estados finales (CERRADA) y
las re-transiciones (ASIGNADA→ASIGNADA) están bloqueados. Un estado nuevo solo requiere
agregar su conjunto de bloqueados al dict, sin tocar las demás reglas.

## Sprint B.5.1 — Hardening

### L-H1: Identidad del actor en callbacks de Telegram

El actor de una acción en un bot de Telegram SIEMPRE debe provenir de `query.from_user.id`.
Nunca embeber el ID del actor en `callback_data` — ese dato viene del cliente y puede ser
manipulado con un cliente modificado. El `callback_data` solo debe llevar identidad de
*objetos* (IDs de incidencias, tipos de acción), nunca del *sujeto* (quién actúa).

### L-H2: Init-time vs call-time en módulos Python

Los imports de módulos que leen `os.environ[...]` (con corchetes) explotan en import-time
si falta la variable de entorno. El patrón correcto es lazy init: variable global a `None`
+ función `_get_client()` que inicializa on-demand con un error controlado. Ver
`transcriber.py` como referencia canónica del patrón.

### L-H3: Tests con efectos externos en import-time

Todo código con efectos externos (llamadas a APIs, I/O real) debe vivir dentro de funciones
`test_*`, no a nivel de módulo. Pytest importa los archivos `test_*.py` durante la fase de
collection — código a nivel de módulo con efectos externos se ejecuta aunque no se pidan
esos tests, aumentando latencia y costo en cada corrida de la suite. Usar
`@pytest.mark.integration` + `addopts = -m "not integration"` en pytest.ini para aislar
estos tests de la suite default.
