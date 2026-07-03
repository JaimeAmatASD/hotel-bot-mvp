"""Summary formatters for individual reports."""
import html

from config.enums import ReportType
from presenters.constants import PRIORIDAD_EMOJI, TIPO_EMOJI


def format_summary(result: dict) -> str:
    tipo = result.get("tipo", ReportType.ERROR)
    prioridad = result.get("prioridad")
    # Estos campos van dentro de parse_mode=HTML: un '<' sin escapar rompe el envío
    ubicacion = html.escape(result.get("ubicacion") or "") or None
    categoria = html.escape(result.get("categoria") or "") or None
    subcategoria = html.escape(result.get("subcategoria") or "") or None
    descripcion = html.escape(result.get("descripcion") or "")

    tipo_emoji = TIPO_EMOJI.get(tipo, "❓")
    prioridad_str = f" — {PRIORIDAD_EMOJI.get(prioridad, '')} {prioridad}" if prioridad else ""

    lines = [f"<b>{tipo_emoji} {tipo}{prioridad_str}</b>"]
    if ubicacion:
        lines.append(f"📍 {ubicacion}")
    if categoria:
        cat_str = f"{categoria} › {subcategoria}" if subcategoria else categoria
        lines.append(f"🏷 {cat_str}")
    lines.append(f"📝 {descripcion}")

    return "\n".join(lines)


def format_summary_with_warning(result: dict) -> str:
    return format_summary(result) + "\n\n⚠️ <i>Tengo dudas sobre la clasificación, confirmá si está bien.</i>"


def format_debug_block(result: dict) -> str:
    lines = ["─────────────", "🔍 <b>Detalles técnicos:</b>"]

    confianza = result.get("confianza")
    if confianza is not None:
        lines.append(f"• Confianza: {round(confianza * 100)}%")

    idioma = result.get("idioma_original")
    if idioma:
        lines.append(f"• Idioma original: {idioma}")

    huesped = result.get("huesped_afectado")
    if huesped is not None:
        lines.append(f"• Huésped afectado: {'sí' if huesped else 'no'}")

    hab = result.get("habitacion_huesped")
    if hab:
        lines.append(f"• Habitación huésped: {hab}")

    nota = result.get("tipo_nota_huesped")
    if nota:
        lines.append(f"• Tipo nota huésped: {nota}")

    subcat = result.get("subcategoria")
    if subcat:
        lines.append(f"• Subcategoría: {subcat}")

    campos = result.get("campos_faltantes") or []
    lines.append(f"• Campos faltantes: {', '.join(campos) if campos else 'ninguno'}")

    return "\n".join(lines)
