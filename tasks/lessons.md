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

### callback_data: solo identidad de objetos, nunca del sujeto

Para callbacks de incidencia: `incident_action:{incident_id}:{sub_action}`.
El actor se obtiene SIEMPRE de `query.from_user.id` — nunca incluirlo en callback_data
porque ese campo viene del cliente y puede manipularse. Ver L-H1 (Sprint B.5.1).
El string resultante (~35 chars) queda bien por debajo del límite de 64 bytes de Telegram.
Regla: mientras el callback_data quepa en 64 bytes, preferir todo en el string sobre
tabla auxiliar. Si supera el límite, ahí sí usar tabla.

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

## Sprint B.8 — Google Sheets sync (2026-05-25)

### L-B8-1: Capa de visibilidad que nunca puede tumbar la fuente de verdad

Cuando se añade un sistema externo como espejo (Sheets, webhook, bus de eventos), el orden
de operaciones es crítico: 1) escribir en la fuente de verdad (SQLite), 2) confirmar al usuario,
3) sync al espejo. Si el paso 3 falla, los pasos 1 y 2 ya pasaron — el dato no se pierde.
Implementación: toda función de sync envuelta en try/except total que loguea pero nunca propaga.
El caller usa `asyncio.create_task()` para disparar el sync como fire-and-forget sin esperar
el resultado. Un fallo de red en Sheets no retarda ni tumba el handler de Telegram.

### L-B8-2: asyncio.to_thread para I/O síncrono en handlers async

gspread es una librería puramente síncrona. Llamarla directamente desde un handler async
bloquea el event loop de python-telegram-bot durante toda la latencia de red (100-500ms),
congelando todos los otros handlers activos. Solución: `asyncio.to_thread(fn_sincrona, args)`
mueve la llamada a un thread del pool del OS, liberando el event loop.
Patrón completo: función síncrona `_sync_*_sync()` + wrapper async `sync_*()` que llama
`await asyncio.to_thread(...)`. El caller usa `asyncio.create_task(sync_*())` para no esperar.

### L-B8-3: Google Sheets API requiere habilitación explícita en GCP

Tener una cuenta de servicio con acceso al spreadsheet NO es suficiente. La Google Sheets API
debe habilitarse explícitamente en el proyecto GCP de esa cuenta de servicio en
`console.developers.google.com/apis/api/sheets.googleapis.com`. Sin esto, el error es un
403 con "API has not been used in project X before or it is disabled" — confuso porque
parece un error de permisos del spreadsheet cuando en realidad es de la API en GCP.

### L-B8-4: Cachear handles de worksheets — no re-abrir en cada llamada

Cada llamada a `spreadsheet.worksheet(name)` hace una request HTTP. Si se cachea el handle
en un dict `_worksheets: dict[str, Worksheet]` con lazy init, solo se abre una vez por
nombre de hoja por ciclo de vida del proceso. El cliente y el spreadsheet también se
cachean como variables de módulo. El patrón: `if name not in _worksheets: ... _worksheets[name] = ws`.

## Refactor integral post-B.8 (2026-05-27)

### L-R1: Detectar duplicación con grep -A antes de extraer un helper

Los 3 handlers (text/audio/photo) tenían `_pop_followup_state` y `_pop_correction_state`
byte-por-byte idénticos (35 LoC × 3 archivos). Si la primera vez que duplicás copy-paste
no extraés el helper, el costo del refactor se multiplica con cada archivo nuevo.
Regla de detección: cuando hagas la 2da copia de una función, parar y mover a un módulo
compartido. La 3ra copia ya es deuda técnica.

### L-R2: StrEnum como migración sin riesgo de magic strings

`StrEnum` (Python 3.11+) hereda de `str`, así que `IncidentState.ABIERTA == "ABIERTA"` es
`True` y SQLite sigue almacenando strings idénticos. Esto permite sustitución gradual:
escribir `IncidentState.ABIERTA` en código nuevo sin migrar las queries SQL ni romper
datos existentes. El beneficio inmediato es autocompletado del IDE y errores de typo
detectables por el linter, sin riesgo a runtime.

### L-R3: init_db() lazy era un patrón defensivo que se convirtió en costo silencioso

Llamar `init_db()` al principio de cada función pública parecía robusto (cada operación
"se asegura" de que el schema existe), pero significa ejecutar 7 `CREATE IF NOT EXISTS` +
varios `PRAGMA table_info` en cada query. Mover el init a una sola llamada en `bot.py`
elimina el overhead. Para los tests, requirió un explícito `storage.init_db()` después
de `monkeypatch.setattr(storage, "DB_PATH", ...)`. Aprendizaje: las llamadas defensivas
en producción se acumulan; mejor un init explícito al startup que un init implícito en
cada query.

### L-R4: asyncio.gather con return_exceptions=True para envío paralelo robusto

Iterar destinatarios con `await` en loop secuencializa lo que puede ser paralelo: si hay
4 destinatarios y cada envío Telegram tarda ~200ms, son 800ms vs 200ms. La versión
correcta es `asyncio.gather(*tasks, return_exceptions=True)`. Sin el flag, una excepción
en cualquier task aborta el resto — con el flag, los demás siguen y los errores se
recolectan como valores de retorno. Para notificaciones, donde "un destinatario falló"
no debe impedir que los otros reciban, este flag es crítico.

### L-R5: Re-exports del paquete __init__.py para preservar API legacy

Cuando se divide `storage.py` (733 LoC) en paquete `storage/`, el archivo `__init__.py`
del paquete debe re-exportar todo lo público:

```python
from storage._conn import DB_PATH, _conn
from storage.classifications import save, get_incident, ...
# ... etc
```

Así los callers existentes (`from storage import save`) siguen funcionando sin tocar nada.
Es la mejor forma de hacer un refactor estructural grande con cero impacto en los callers.

### L-R6: DB_PATH compartido entre __init__ y submódulos — lectura dinámica

Cuando el paquete `storage/` re-exporta `DB_PATH` desde `storage/_conn.py`, los tests que
hacen `patch.object(storage, "DB_PATH", new_path)` patchean el namespace del paquete,
no el de `_conn.py`. Solución: en `_conn()`, leer DB_PATH dinámicamente del package
namespace:

```python
def _conn():
    import storage
    db_path = getattr(storage, "DB_PATH", DB_PATH)
    ...
```

Esto preserva la API de patcheo existente sin migrar todos los tests.

### L-R7: Mocks en tests apuntan al módulo donde se USA el símbolo, no donde se define

Al mover `get_debug_mode` de `text_handler.py` a `_flow.py`, los tests que hacían
`patch("handlers.text_handler.get_debug_mode")` empezaron a fallar con AttributeError.
La regla de Python mock: `patch("module.X")` requiere que `X` exista como atributo
en `module`. Si `text_handler.py` ya no importa `get_debug_mode`, no se puede patchear ahí.
La corrección es patchear `handlers._flow.get_debug_mode` (donde sí se importa y se usa).
Esto es independiente de dónde se DEFINE la función — siempre se patchea donde se LEE.

### L-R8: Port + concrete adapter + as_sender() — abstracción mínima, máximo retorno

Para abstraer `bot.send_message`/`send_photo` detrás de un port `MessageSender`, el patrón
costó ~50 LoC: ABC con 2 métodos, impl Telegram concreta, helper `as_sender()` que
wrappa duck-type. Beneficios:
- Tests pueden usar `FakeMessageSender` que registra llamadas sin mockear python-telegram-bot.
- Día que se quiera meter WhatsApp/Slack: nuevo adapter, dispatch intacto.
Regla: una abstracción justifica su costo cuando elimina el mock de un framework grande
o cuando hay 2+ implementaciones reales en el horizonte.

### L-R9: Dataclasses opcionales — adopción gradual sin migración masiva

Crear `domain/entities.py` con `@dataclass Employee, Incident` no obliga a migrar los
callers que usan dicts. Los entities tienen `from_dict()/from_row()` y conviven con el
patrón dict por el tiempo que haga falta. Los tests nuevos los usan directamente
(`Employee(telegram_id=1, nombre="X", ...)` es más legible que un dict de 5 campos).
Migración real ocurre solo donde aporta — sin Big-Bang. Aprendizaje: una mejora opt-in
puede sembrarse meses antes de ser obligatoria.

### L-R10: Cuándo NO hacer Clean Architecture

Después del refactor A/B/C el código ya estaba en 4 capas implícitas (domain en
`permissions`+`config`, application en `brain`+`report_processor`, adapters en
`storage`+`notifier`+`sheets_sync`, presentation en `handlers`). Pasar a Clean Architecture
ortodoxo (ports + ABCs + DI container + mappers) habría sumado ~40% de LoC en ceremonia
para un beneficio marginal en un proyecto de un dev con un bot.
Regla: Clean Arch justifica su costo cuando hay (a) equipo grande, (b) bounded contexts
múltiples, (c) intención real de swapear adapters (provider IA, base de datos, canal).
Para un MVP solo, separar por capas mediante paquetes con re-exports es suficiente.

## Testing hotelero pre-piloto (2026-05-28)

### L-T1: Automatizar escenarios operativos, no solo unidades técnicas

Los tests unitarios cubrían piezas sueltas (permisos, notificaciones, reportes, queries),
pero faltaba una prueba que pensara como hotelero: empleado reporta, confirma, encargado
toma/cierra, gerente consulta, reporte de turno queda auditable. `tests/test_hotel_scenarios.py`
cubre esos flujos con SQLite temporal y mocks de Telegram/IA/Sheets. Beneficio: detecta
roturas entre capas aunque cada módulo aislado siga pasando.

### L-T2: Tests E2E fake deben cortar la red en los bordes correctos

Para que el protocolo sea determinista, se parchean solo los bordes externos:
`process_message` (IA), `notify_incident`/`notify_employee_state_change` (Telegram),
y `sheets_sync.sync_*` (Google Sheets). La lógica real que queda bajo prueba es la valiosa:
handlers, storage, permisos, formateo, eventos, reportes y queries.

### L-T3: `/historial` descubrió un import faltante que la suite vieja no ejercitaba

`handle_historial()` usaba `permissions.can_see_incident(...)`, pero el módulo
`handlers/command_handler.py` solo importaba funciones concretas desde `permissions`, no
el módulo `permissions`. Los tests anteriores probaban permisos y formatters por separado,
pero no el comando real. El escenario "empleado no puede leer historial ajeno" lo detectó.
Regla: cualquier comando crítico debe tener al menos un test que invoque el handler real.

### L-T4: Fixtures de integration deben apuntar al layout real del repo

Los tests de audio buscaban fixtures en `tests/integration/audios/`, pero los `.flac`
versionados viven en `audios/`. Eso hacía que se saltaran dos tests reales aunque los
fixtures existieran. La ruta correcta es desde `tests/integration/test_brain.py` hacia
la raíz del repo: `Path(__file__).parent.parent.parent / "audios"`.

## Work-order lifecycle + informes de turno (2026-06/07)

### L-W1: Máquina de estados en un solo módulo de config, transición en una sola función

Con 6 estados y 8 verbos, la tentación es chequear transiciones en cada handler.
En su lugar: `config/transitions.py` define `ACTION_TO_STATE` y `EXPECTED_FROM` (única
fuente de verdad declarativa) y `update_incident_state_atomic(action=...)` en
`storage/events.py` es la ÚNICA función que muta estado — valida contra la tabla,
escribe trazabilidad (`assigned_by/resolved_by/closed_by/cancelled_by`) y registra el
evento en la misma transacción. Agregar un verbo nuevo = tocar la tabla, no los handlers.

### L-W2: Renombrar un estado en producción — migración de datos + grep de literales

Renombrar `ABIERTA` → `NUEVA` requirió tres frentes que se olvidan por separado:
1) UPDATE de las filas existentes en la migración de schema, 2) grep de literales
residuales en código (`948ce5e`), 3) grep de literales en tests (`4581bb7`).
Los tests con el string viejo hardcodeado pasaban contra fixtures nuevos y ocultaban
el bug. Regla: al renombrar un valor de dominio, grep global del literal viejo en
TODO el repo antes de dar por cerrado el cambio.

### L-W3: Pasos intermedios opcionales en flujos operativos (EN_PROCESO)

En el hotel real, el empleado a veces marca "comenzar" y a veces va directo a "terminado".
Forzar el paso intermedio agrega fricción sin valor. La tabla `EXPECTED_FROM` acepta
`terminado` tanto desde `ASIGNADA` como desde `EN_PROCESO`. Regla: modelar los estados
que la operación necesita auditar, no los que el diagrama sugiere como "completos".

### L-W4: Feature flag de entorno para pilotos graduales

`REPORT_NOTIFY_GERENTE=false` (default off) gatea el aviso automático al gerente al cerrar
un informe de turno. Permite desplegar todo el código y activar el comportamiento por
entorno cuando el piloto intra-sector lo valide, sin rama aparte ni redeploy de código.
El test del filtro se ejercita con el flag ON explícito para no depender del default.

### L-W5: Comandos de lectura agregada (rollup) — read-only estricto

`/reporte sector` consolida clasificaciones recientes del sector sin tocar estado:
`get_classifications_recent()` es solo SELECT y el formato reusa las mismas secciones
compartidas del informe individual. Regla: un comando de consulta jamás muta — si el
rollup necesitara "marcar como visto", eso es otra feature con su propia transición.

## Sprint C.1 — Rediseño del informe de turno (2026-08-09)

**Una ventana deslizante + un filtro de "ya consolidado" pierde datos en silencio.**
`/reporte` tomaba las últimas 12h y excluía lo que ya tuviera `report_id`. Con uso esporádico
(testeo semanal), cada sesión caía fuera de la ventana antes del siguiente `/reporte`: 16 de 39
clasificaciones no entraron jamás en un informe, y 14 eran ya inalcanzables. El síntoma que ve el
usuario es "no hay nada que reportar"; la causa está dos capas más abajo, en el WHERE.
Lección general: cuando el criterio de una consulta es temporal Y de estado, verificá qué pasa con
las filas que caen fuera de los dos. Si no hay forma de recuperarlas, es pérdida de datos.

**Poner el invariante en el esquema, no en el handler.** "Un informe por persona por día" es un
`UNIQUE INDEX`, no un `if` antes del INSERT. El índice además destapó el duplicado histórico
(REP-003/REP-004, los dos de Juan del 01/07) que un `if` nuevo habría dejado enterrado.

**Migrar con un índice único ya creado requiere bajarlo primero.** Poblar la columna que indexa
pasa necesariamente por un estado intermedio con duplicados — que son justamente los que la
migración viene a fusionar. `DROP INDEX` → poblar → deduplicar → `CREATE INDEX`.

**`init_db()` no corre migraciones.** `CREATE TABLE IF NOT EXISTS` es no-op sobre una base que ya
existe, así que una columna nueva necesita ALTER explícito en `schema.py` *además* de la migración.
Y como `init_db()` corre antes que `apply_pending()` en `bot.py`, olvidarlo rompe el arranque.

**No deduzcas del dato lo que quien llama ya sabe.** La marca ↩ de arrastre se calculaba comparando
la fecha del ítem contra la de `items[0]`. Con cero ítems cargados hoy no había contra qué comparar
y la marca desaparecía justo cuando más importaba. Pasarlo como flag desde el llamador lo arregló y
borró el caso borde.

**Dimensionar con datos reales antes de diseñar la vista.** El arrastre se estimó en 3 mirando los
huérfanos; en la base real eran 13, porque el criterio correcto es "sigue abierta", no "nunca se
consolidó". De ahí salió el tope de 5 con contador.

**Sacar un botón puede matar un subsistema entero.** Quitar "Corregir un ítem" del informe dejó
`awaiting_correction_item` sin nadie que lo seteara, y con él `handlers/_corrections.py` completo
(112 líneas) más su cableado en `text_handler` y `audio_handler`. No tenía un solo test. Cuando
saques un punto de entrada, grepeá quién escribe la bandera que lo activa.
