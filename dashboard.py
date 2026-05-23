import json
import os
import streamlit as st
import pandas as pd
from classifier import classify, _get_client, SYSTEM_PROMPT
from google.genai import types
from test_cases import TEST_CASES
import storage

st.set_page_config(page_title="Hotel Bot — Clasificador", layout="wide")
st.title("Hotel Bot — Clasificador de Mensajes")

TIPO_COLORS = {
    "INCIDENCIA": "🔴",
    "OBSERVACION": "🟡",
    "GUEST_INTEL": "🔵",
    "NO_REPORTE": "⚪",
    "ERROR": "❌",
}
PRIORIDAD_COLORS = {
    "CRITICA": "🚨",
    "ALTA": "🔺",
    "MEDIA": "🟠",
    "BAJA": "🟢",
}

if "history" not in st.session_state:
    st.session_state.history = []

tab_manual, tab_tests, tab_employees = st.tabs([
    "✍️ Probar mensaje", "🧪 Correr tests", "👥 Empleados"
])

# ── TAB 1: Clasificación manual ──────────────────────────────────────────────
with tab_manual:
    with st.form("classify_form"):
        message = st.text_area("Mensaje del empleado", height=100,
                               placeholder="Ej: Hay un goteo en el aire acondicionado de la 204")
        col1, col2, col3 = st.columns(3)
        with col1:
            nombre = st.text_input("Nombre", value="Ana")
        with col2:
            departamento = st.selectbox("Departamento",
                ["HOUSEKEEPING", "RECEPCION", "MANTENIMIENTO", "RESTAURANTE", "OTRO"])
        with col3:
            idioma = st.selectbox("Idioma", ["es", "en", "ro", "fr", "de", "other"])
        submitted = st.form_submit_button("Clasificar", use_container_width=True, type="primary")

    if submitted and message.strip():
        employee = {"nombre": nombre, "departamento": departamento, "idioma": idioma}
        with st.spinner("Clasificando..."):
            result = classify(message, employee)

        tipo = result.get("tipo", "ERROR")
        prioridad = result.get("prioridad")

        col1, col2, col3 = st.columns(3)
        col1.metric("Tipo", f"{TIPO_COLORS.get(tipo, '❓')} {tipo}")
        col2.metric("Prioridad", f"{PRIORIDAD_COLORS.get(prioridad, '')} {prioridad}" if prioridad else "—")
        col3.metric("Confianza", f"{result.get('confianza', 0):.0%}" if result.get('confianza') else "—")

        st.markdown("**Descripción**")
        st.info(result.get("descripcion", "—"))

        col1, col2 = st.columns(2)
        with col1:
            if result.get("ubicacion"):
                st.markdown(f"📍 **Ubicación:** {result['ubicacion']}")
            if result.get("categoria"):
                st.markdown(f"🏷️ **Categoría:** {result['categoria']}")
            if result.get("subcategoria"):
                st.markdown(f"↳ {result['subcategoria']}")
        with col2:
            if result.get("habitacion_huesped"):
                st.markdown(f"🛏️ **Habitación huésped:** {result['habitacion_huesped']}")
            if result.get("tipo_nota_huesped"):
                st.markdown(f"👤 **Nota huésped:** {result['tipo_nota_huesped']}")
            if result.get("huesped_afectado") is not None:
                st.markdown(f"👥 **Huésped afectado:** {'Sí' if result['huesped_afectado'] else 'No'}")

        if result.get("campos_faltantes"):
            st.warning("**Campos faltantes:** " + ", ".join(result["campos_faltantes"]))

        with st.expander("JSON completo"):
            st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")

        storage.save(employee, message, result)
        st.session_state.history.append({
            "Mensaje": message[:60] + ("…" if len(message) > 60 else ""),
            "Tipo": f"{TIPO_COLORS.get(tipo, '❓')} {tipo}",
            "Prioridad": f"{PRIORIDAD_COLORS.get(prioridad, '')} {prioridad}" if prioridad else "—",
            "Confianza": f"{result.get('confianza', 0):.0%}" if result.get('confianza') else "—",
            "Descripción": result.get("descripcion", "—"),
        })

    elif submitted:
        st.warning("Escribe un mensaje antes de clasificar.")

    if st.session_state.history:
        st.markdown("---")
        st.markdown("### Historial de la sesión")
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("Limpiar", use_container_width=True):
                st.session_state.history = []
                st.rerun()
        st.dataframe(
            pd.DataFrame(st.session_state.history[::-1]),
            use_container_width=True, hide_index=True,
        )

# ── TAB 2: Runner de tests ────────────────────────────────────────────────────
with tab_tests:
    st.markdown("Corre los 20 casos de prueba y muestra resultados.")
    if st.button("▶️ Correr todos los tests", type="primary"):
        results = []
        passed = 0
        progress = st.progress(0, text="Clasificando...")
        for i, tc in enumerate(TEST_CASES):
            r = classify(tc["message"], tc["employee"])
            ok = r.get("tipo") == tc["expected_tipo"]
            if ok:
                passed += 1
            results.append({
                "ID": tc["id"],
                "✓": "✅" if ok else "❌",
                "Esperado": tc["expected_tipo"],
                "Obtenido": r.get("tipo", "ERROR"),
                "Conf.": f"{r.get('confianza', 0):.0%}" if r.get('confianza') else "—",
                "Mensaje": tc["message"][:55] + ("…" if len(tc["message"]) > 55 else ""),
            })
            progress.progress((i + 1) / len(TEST_CASES), text=f"{i+1}/{len(TEST_CASES)} clasificados…")
        progress.empty()
        st.metric("Accuracy", f"{passed}/{len(TEST_CASES)} ({passed/len(TEST_CASES):.0%})",
                  delta=f"{passed - 17} vs umbral mínimo (17)")
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True,
                     column_config={"✓": st.column_config.TextColumn(width="small")})

# ── TAB 3: Empleados ──────────────────────────────────────────────────────────
with tab_employees:
    employees = storage.get_employees()

    if not employees:
        st.info("Aún no hay datos. Clasificá algunos mensajes en la pestaña 'Probar mensaje' primero.")
        st.stop()

    col_list, col_detail = st.columns([1, 3])

    with col_list:
        st.markdown("### Empleados")
        names = [e["employee_name"] for e in employees]
        selected = st.radio("Seleccionar", names, label_visibility="collapsed")

    with col_detail:
        stats = storage.get_employee_stats(selected)

        st.markdown(f"## {selected}")
        st.caption(f"Depto: {stats['recent'][0]['employee_dept'] or '—'} · Último mensaje: {stats['last_seen']}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Mensajes", stats["total"])
        c2.metric("Sin habitación", f"{stats['missing_room_pct']}%",
                  help="% de mensajes donde faltó el número de habitación o ubicación")
        c3.metric("Confianza baja", f"{stats['low_confidence_pct']}%",
                  help="% de mensajes con confianza < 80%")
        most_common = max(stats["tipo_counts"], key=stats["tipo_counts"].get) if stats["tipo_counts"] else "—"
        c4.metric("Tipo más frecuente", TIPO_COLORS.get(most_common, "") + " " + most_common)

        st.markdown("#### Distribución de tipos")
        tipo_df = pd.DataFrame(
            [{"Tipo": k, "Mensajes": v} for k, v in stats["tipo_counts"].items()]
        ).sort_values("Mensajes", ascending=False)
        st.bar_chart(tipo_df.set_index("Tipo"))

        if stats["top_missing"]:
            st.markdown("#### Campos que más faltan")
            miss_df = pd.DataFrame(stats["top_missing"], columns=["Campo", "Veces"])
            st.dataframe(miss_df, use_container_width=True, hide_index=True)

        st.markdown("#### Últimos mensajes")
        recent_df = pd.DataFrame([{
            "Fecha": r["timestamp"][:16],
            "Mensaje": r["message"][:70] + ("…" if len(r["message"]) > 70 else ""),
            "Tipo": TIPO_COLORS.get(r["tipo"], "") + " " + (r["tipo"] or ""),
            "Prioridad": r["prioridad"] or "—",
            "Faltó": r["campos_faltantes"],
        } for r in stats["recent"]])
        st.dataframe(recent_df, use_container_width=True, hide_index=True)

        st.markdown("---")

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("#### Informe individual")
            if st.button(f"Generar informe de {selected}", use_container_width=True):
                prompt = f"""Eres el asistente del gerente de un hotel boutique.
Analiza el historial de mensajes del empleado '{selected}' y genera un informe breve (máximo 200 palabras) con:
1. Cómo usa el bot (tipos de reportes que manda, calidad de la información)
2. Patrones negativos detectados (qué suele olvidar, mensajes ambiguos)
3. Una recomendación concreta para que mejore su uso del bot

Datos del empleado:
- Total mensajes: {stats['total']}
- Distribución tipos: {stats['tipo_counts']}
- % sin habitación/ubicación: {stats['missing_room_pct']}%
- Campos que más olvida: {stats['top_missing']}
- % mensajes con confianza baja: {stats['low_confidence_pct']}%
- Últimos mensajes: {[r['message'] for r in stats['recent'][:5]]}

Escribe el informe en español, tono profesional pero directo."""

                with st.spinner("Generando informe..."):
                    response = _get_client().models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction="Eres el asistente del gerente de un hotel. Responde solo con el informe, sin títulos extra ni markdown."
                        )
                    )
                st.text_area("Informe", response.text, height=280, label_visibility="collapsed")

        with col_b:
            st.markdown("#### Informe para gerencia")
            if st.button("Generar informe global", use_container_width=True):
                all_emp = [storage.get_employee_stats(e["employee_name"]) for e in employees]
                resumen = [{
                    "nombre": s["name"],
                    "total": s["total"],
                    "tipos": s["tipo_counts"],
                    "sin_habitacion_pct": s["missing_room_pct"],
                    "campos_faltantes_top": s["top_missing"],
                } for s in all_emp]

                prompt = f"""Eres el asistente del gerente de un hotel boutique.
Genera un informe ejecutivo (máximo 300 palabras) sobre el uso del bot de reportes por parte del equipo.
Incluye:
1. Resumen general del equipo
2. Empleados que más reportan y los que menos
3. Problemas comunes detectados en los mensajes (qué suele faltar)
4. Recomendaciones para mejorar la calidad de los reportes

Datos del equipo:
{json.dumps(resumen, ensure_ascii=False, indent=2)}

Escribe en español, tono ejecutivo, para que el gerente lo lea en 2 minutos."""

                with st.spinner("Generando informe..."):
                    response = _get_client().models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction="Eres el asistente del gerente de un hotel. Responde solo con el informe."
                        )
                    )
                st.text_area("Informe gerencial", response.text, height=280, label_visibility="collapsed")
