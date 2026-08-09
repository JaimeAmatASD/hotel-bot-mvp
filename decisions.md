# Decisiones

Elecciones de peso con su razón. No errores (eso es `tasks/lessons.md`): bifurcaciones
donde se podía ir para dos lados y se eligió uno.

Sirve para no reconstruir de memoria por qué hiciste lo que hiciste.

Formato: contexto, alternativas descartadas, qué se eligió, **qué se pierde**, y qué
tendría que pasar para reabrirla. Si no hay costo, no era una decisión difícil.

---

## 2026-08 — El informe de turno es por día calendario, no por ventana de horas

**Contexto**: `/reporte` tomaba las últimas 12h y excluía lo ya consolidado. Con uso
esporádico, cada sesión caía fuera de la ventana antes del siguiente `/reporte`: 16 de
39 clasificaciones no entraron jamás en un informe.
**Alternativas**: ventana configurable por el usuario (sigue siendo arbitraria); traer
todo lo no consolidado sin límite (el primer informe tiraba seis semanas de golpe).
**Elegido**: día calendario (00:00 → ahora) más arrastre de incidencias abiertas de
días anteriores, sin filtrar por `report_id`.
**Costo aceptado**: un turno nocturno que cruza medianoche queda partido en dos
informes. Con piloto diurno de dos personas no molesta.
**Se revisa si**: entra gente con turno de noche.

## 2026-08 — "Un informe por persona por día" vive en el esquema, no en el código

**Contexto**: al permitir re-cerrar el informe del día hacía falta garantizar que no se
crearan dos.
**Alternativas**: chequear con un `if` antes del INSERT.
**Elegido**: `UNIQUE INDEX idx_reports_employee_day` en `reports`.
**Costo aceptado**: la migración se complica — hay que bajar el índice para poder
poblar la columna, porque el paso intermedio tiene duplicados. Y destapó un duplicado
histórico (REP-003/REP-004) que hubo que fusionar.
**Se revisa si**: nunca; el índice ya encontró un bug que un `if` habría tapado.

## 2026-08 — El arrastre de pendientes se topea en 5

**Contexto**: con datos reales el arrastre eran 13 incidencias abiertas, algunas de
hace más de un mes.
**Alternativas**: mostrarlas todas (máxima presión, informe ilegible); filtrar por
prioridad (una BAJA vieja desaparece para siempre); ventana de 7 días (deja de verse
justo lo más podrido).
**Elegido**: las 5 más viejas más un contador `…y N más abiertas · /abiertas`.
**Costo aceptado**: hay que entrar a `/abiertas` para ver el resto.
**Se revisa si**: el arrastre baja de 5 de forma sostenida (señal de que se están
cerrando), o sube tanto que el contador pierde sentido.

---

<!-- Las que todavía no están escritas y conviene anotar cuando se toquen:
     - por qué gemini-2.5-flash y no otro modelo (costo vs calidad vs latencia)
     - qué pasa cuando Gemini o Groq se caen o tardan (hoy: health-check al arranque,
       pero no hay política de reintento en caliente)
     - por qué SQLite es la fuente de verdad y Sheets solo espejo -->
