# Audios de prueba para Whisper

Tenés que grabar 5 audios cortos (5-15 segundos cada uno) y guardarlos en esta carpeta con los nombres exactos. Podés grabarlos con cualquier app: la grabadora de tu móvil, Telegram a tu propio chat (descargás el audio y lo movés acá), Audacity, lo que sea.

**Formato aceptado:** .ogg, .mp3, .m4a, .wav. Mejor todos en el mismo formato pero no es obligatorio.

## Frases a grabar

### 1. `es_incidencia_204.ogg` — español, voz normal
> "Hay un goteo en el aire acondicionado de la 204"

### 2. `es_guest_intel_aniversario.ogg` — español, voz casual
> "Los de la 302 están de aniversario hoy"

### 3. `en_overflow_207.ogg` — inglés, acento natural (no hace falta nativo)
> "Room 207 toilet is clogged, water is overflowing"

### 4. `en_observation_pillows.ogg` — inglés
> "Guests ask for extra pillows almost every day, we should keep more in stock"

### 5. `ro_ac_105.ogg` — rumano
> "Camera 105 are o problemă cu aerul condiționat, nu funcționează"

Si no sabés rumano: pedile a Google Translate que lea la frase, o a alguien rumano que la grabe, o usá un sintetizador TTS online (https://ttsmp3.com tiene voces en rumano gratis). Para validación de MVP, TTS sirve.

## Después de grabarlos

Volvé al chat y avisá. El siguiente paso es:

```bash
python evaluate_audio.py
```
