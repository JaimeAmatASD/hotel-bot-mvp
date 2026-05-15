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
