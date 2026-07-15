# Cambiar el motor de traducción

El sistema traduce las actividades de español a EN/FR/DE. El motor está
aislado en UN solo nodo del workflow n8n
(stack/n8n/flujo-actividades-traduccion.json, nodo "Traducir"), de modo
que cambiarlo no afecta al resto del flujo. Español es siempre el
original; las traducciones se regeneran salvo las marcadas "revisado".

## Motor actual: DeepL API Free (0 €)
- Alta: https://www.deepl.com/pro-api (plan Free, 500.000 caracteres/mes).
- Da una Auth Key. Ponerla en el entorno de n8n como `DEEPL_KEY`
  (NUNCA en el repo; va en el .env del VPS).
- Endpoint: https://api-free.deepl.com/v2/translate
- Cabecera: `Authorization: DeepL-Auth-Key <DEEPL_KEY>`
- Cuerpo (form-urlencoded): text, source_lang=ES, target_lang=EN|FR|DE
- Respuesta: `{"translations":[{"text":"..."}]}`

## Cómo cambiar de motor (procedimiento)
1. En n8n, abrir el workflow "Actividades multiidioma".
2. Localizar el nodo **"Traducir (DeepL)"**. Es el único a tocar.
3. Sustituir según el motor elegido (ejemplos abajo). El nodo siguiente
   ("Reagrupar") espera encontrar el texto traducido; ajustar ahí la
   ruta de extracción del texto si el nuevo motor responde distinto.
4. Guardar el workflow. Nada más del sistema cambia.
5. Actualizar la variable de entorno de la clave en el .env del VPS y
   reiniciar n8n (`docker compose up -d n8n`).

### Opción: Google Cloud Translation
- Endpoint: https://translation.googleapis.com/language/translate/v2
- Auth: `?key=<GOOGLE_KEY>` en la URL.
- Cuerpo JSON: {q, source:"es", target:"en", format:"text"}
- Respuesta: `data.translations[0].translatedText`
- Coste: 500k car/mes gratis 1er año, luego ~20 $/millón.

### Opción: LLM barato (calidad marketing)
Sustituir el nodo HTTP por una llamada al chat del proveedor (Anthropic,
OpenAI, Mistral, DeepSeek...). Ventaja: se le puede dar contexto:
  system: "Traduce del español al {idioma}. Tono cálido y cercano para
  un público de residentes extranjeros en la Costa del Sol. NO traduzcas
  los términos: Hatha yoga, Iyengar, SUP yoga. Devuelve solo la traducción."
  user: {texto español}
- Respuesta: el texto del mensaje del modelo.
- Coste: céntimos/año al volumen de Julia. Requiere clave de API del
  proveedor (de pago, aparte de cualquier suscripción de chat).

### Opción: LibreTranslate (autoalojado, 0 € y sin terceros)
- Añadir un contenedor libretranslate al stack y apuntar el nodo a
  http://libretranslate:5000/translate. Cero dependencia externa, pero
  calidad inferior a DeepL. Coherente con la filosofía self-hosted si
  algún día se quiere cortar toda dependencia de APIs externas.

## Recomendación
Empezar con DeepL Free (mejor relación calidad/0€ para es→de/fr). Si una
traducción concreta chirría, pasar a LLM barato solo si compensa. El
cambio son 5 minutos en un nodo.
