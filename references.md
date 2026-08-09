# Referencias

Ejemplos concretos de "que salga así" y "esto no". Acá rinde más que en ningún lado: la
suite verifica estructura, no si un informe se lee bien en un celular. Un anti-ejemplo
enseña más que tres párrafos de convención.

Cada vez que el bot produzca algo notablemente bien o notablemente mal, pegalo acá.

---

## Informe de turno

**Como esto** (sprint C.1, 2026-08-09):

```
📋 INFORME DE TURNO — (borrador)
👤 Jaime A · MANTENIMIENTO
🕐 09/08 · 11:03–11:59 · 3 ítems

⚠️ QUEDA PENDIENTE (7)
• INC-001 · Hab 9 — Perro no autorizado se coló en habitación 9, durmiendo en c… · ALTA · 🆕 NUEVA · ↩ 29/06
• INC-011 · Hab 4 — Faltan amenities en la Habitación 4. · ALTA · 🆕 NUEVA · ↩ 01/07
…y 2 más abiertas · /abiertas para verlas
──────────────────────────
🔧 INCIDENCIAS (3)
1. Hab 105 — Gotera en habitación 105, se necesitarán materiales… · ALTA · ✅ CERRADA · huésped afectado
──────────────────────────
```

Por qué está bien: lo que falta se lee primero y cada pendiente trae su ID accionable
(`INC-001`), así que se puede actuar sin ir a buscarlo. El `↩ 29/06` dice hace cuánto
está abierta sin que haya que calcularlo. El total real (7) se dice aunque solo se
muestren 5.

**Esto no** — mostrar el arrastre completo:

```
⚠️ QUEDA PENDIENTE (13)
• INC-001 · …
• INC-010 · …
• INC-011 · …
   [13 líneas]
──────────────────────────
🔧 INCIDENCIAS (3)
```

Qué lo arruina: con 13 pendientes arrastradas, lo que pasó hoy queda debajo de tres
pantallas de scroll. El informe del día deja de ser el informe del día. Un "escape de
gas" abierto hace un mes se pierde entre otras doce líneas iguales en vez de destacarse.
De acá salió el tope de 5 con contador (`_MAX_CARRYOVER` en `report_processor.py`).

## Casos borde

<!-- Pegá acá cómo tiene que salir cada uno cuando aparezcan:
     - El empleado manda un audio en rumano o inglés.
     - El mensaje no es un reporte (charla suelta) → NO_REPORTE, sin ruido.
     - Falta la ubicación → el followup pregunta una sola cosa, no un formulario.
     - La API de Gemini se cae en medio de un reporte.
     - Alguien no registrado le escribe al bot. -->

<!-- Diez ejemplos alcanzan. Treinta no los lee nadie. -->
