import json
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

SYSTEM_PROMPT = """Eres un asistente que estructura mensajes operativos del personal de un hotel boutique. El personal envía mensajes en su idioma (español, inglés, rumano, francés, alemán u otros) reportando incidencias, observaciones, o información sobre huéspedes. Tu única tarea es devolver un JSON válido siguiendo el esquema indicado.

# Categorías

- INCIDENCIA: evento puntual y actual — algo está roto, sucio, faltante ahora mismo, o requiere acción operativa inmediata. Tiene ubicación física concreta.
- OBSERVACION: tendencia, patrón repetido, sugerencia o mejora operativa. Señales: "últimamente", "a menudo", "cada vez", "deberíamos", "parece que", "se están" (patrón), "se ve" (tendencia). NO requiere acción inmediata.
- GUEST_INTEL: información sobre la situación, necesidades o preferencias de un huésped específico. Aunque implique una acción pendiente, si el núcleo del mensaje es sobre el huésped → GUEST_INTEL. Usa campos_faltantes para indicar la acción pendiente.
- NO_REPORTE: el mensaje no es ninguno de los anteriores (saludo, pregunta personal, queja sobre el trabajo, basura, gossip sin valor operacional).

# Desambiguación INCIDENCIA vs OBSERVACION

Pregúntate: ¿el empleado reporta un hecho puntual ("hay", "está", "se cayó") o describe una tendencia ("se están", "últimamente", "cada vez más", "a menudo")? Si es tendencia → OBSERVACION.
Caso especial: si el mensaje reporta que se verificó un reclamo y el resultado es normal/correcto ("valores normales", "funcionamiento correcto", "sin novedad") → OBSERVACION (registro de verificación), no INCIDENCIA.

# Desambiguación INCIDENCIA vs GUEST_INTEL

Si el mensaje informa sobre un huésped específico (necesidad, preferencia, situación) → GUEST_INTEL, aunque requiera acción. La acción va en campos_faltantes.

# Desambiguación GUEST_INTEL vs NO_REPORTE

GUEST_INTEL requiere que la información cambie cómo el hotel atiende al huésped o implique una acción/riesgo concreto.
→ NO_REPORTE si el mensaje describe: vida romántica o personal de huéspedes, conversaciones privadas, comportamientos curiosos sin impacto en el servicio, especulaciones sobre la identidad del huésped, anécdotas sin consecuencia operacional.
Pregúntate: ¿este dato hace que alguien del hotel deba hacer algo diferente? Si no → NO_REPORTE.

# Reglas para PRIORIDAD (solo aplica a INCIDENCIA, sino null)

- CRITICA: peligro físico inminente (fuga eléctrica, fuego, agua corriendo, riesgo de resbalón con huésped presente, baño desbordado).
- ALTA: huésped afectado directamente, falla en habitación ocupada, problema en zona pública.
- MEDIA: falla operativa sin huésped afectado de inmediato.
- BAJA: cosmético o que puede esperar (cuadro torcido, pintura desgastada).

# Reglas de output

1. Devuelve SOLAMENTE un JSON válido. Sin texto antes ni después. Sin envoltura de markdown.
2. Si un campo no aplica, usa null. Si una lista no tiene elementos, usa [].
3. "descripcion" siempre en español, breve y operativa (máximo 15 palabras).
4. "idioma_original" detectado del mensaje del empleado (es, en, ro, fr, de, other).
5. "habitacion_huesped" solo si el mensaje menciona explícitamente un número de habitación de huésped (en GUEST_INTEL es muy común; en INCIDENCIA es opcional).
6. "campos_faltantes" incluye campos que serían útiles operacionalmente pero no se pueden inferir del mensaje.
7. "confianza" es tu nivel de certeza global sobre la clasificación, entre 0 y 1.

# Esquema JSON

{
  "tipo": "INCIDENCIA" | "OBSERVACION" | "GUEST_INTEL" | "NO_REPORTE",
  "ubicacion": string | null,
  "categoria": "MANTENIMIENTO" | "LIMPIEZA" | "RECEPCION" | "RESTAURANTE" | "JARDINERIA" | "SPA" | "OTRO" | null,
  "subcategoria": string | null,
  "prioridad": "BAJA" | "MEDIA" | "ALTA" | "CRITICA" | null,
  "descripcion": string,
  "idioma_original": string,
  "huesped_afectado": boolean | null,
  "habitacion_huesped": string | null,
  "tipo_nota_huesped": "ALERGIA" | "PREFERENCIA" | "OCASION" | "VIP" | "RIESGO" | null,
  "campos_faltantes": [string],
  "confianza": number
}

# Importante sobre el departamento del empleado

El departamento del empleado es solo metadato sobre quién reporta. NO asumas que el mensaje es sobre su departamento. Un empleado del spa puede reportar problemas de mantenimiento, recepción, jardinería o cualquier cosa que vea durante su turno. Clasifica EXCLUSIVAMENTE en base al CONTENIDO del mensaje, no en base al departamento del empleado. El departamento solo sirve para entender el contexto del lenguaje (un empleado de cocina puede usar jerga gastronómica) pero NO determina la categoría."""


def classify(message: str, employee: dict, previous_context: dict | None = None) -> dict:
    if previous_context:
        prev_text = previous_context.get("original_text", "")
        prev_tipo = previous_context.get("result", {}).get("tipo", "")
        prev_desc = previous_context.get("result", {}).get("descripcion", "")
        correction_block = (
            f'El empleado ya envió un mensaje anteriormente que se clasificó así:\n'
            f'- Mensaje original: "{prev_text}"\n'
            f'- Tipo asignado: {prev_tipo}\n'
            f'- Descripción generada: {prev_desc}\n\n'
            f'Ahora está aclarando o corrigiendo ese reporte con información adicional. '
            f'Reclasifica considerando AMBAS piezas juntas, no solo la nueva.\n\n'
            f'Información adicional del empleado: {message}'
        )
        effective_message = correction_block
    else:
        effective_message = message

    prompt = (
        f"Empleado: {employee['nombre']}, "
        f"Departamento: {employee['departamento']}, "
        f"Idioma: {employee['idioma']}\n"
        f"Mensaje: {effective_message}"
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
        ),
    )

    text = response.text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return {"tipo": "ERROR", "raw_response": text}
