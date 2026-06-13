import os
import re
import requests
import datetime
from groq import Groq
from PIL import Image, ImageDraw
import io

# ── Configuración ──────────────────────────────────────────────
GROQ_API_KEY         = os.environ["GROQ_API_KEY"]
LINKEDIN_TOKEN       = os.environ["LINKEDIN_ACCESS_TOKEN"]
LINKEDIN_PERSON_URN  = os.environ["LINKEDIN_PERSON_URN"] 
HF_TOKEN             = os.environ["HF_TOKEN"]

# Asegurar que el formato base para perfiles modernos sea "urn:li:person:..."
if not LINKEDIN_PERSON_URN.startswith("urn:li:person:"):
    LINKEDIN_PERSON_URN = f"urn:li:person:{LINKEDIN_PERSON_URN.split(':')[-1]}"

TOPICS = [
    "inteligencia artificial en negocios",
    "productividad con herramientas digitales",
    "liderazgo en la era tecnológica",
    "automatización de procesos",
    "tendencias tech 2025",
]

# ── 1. Elegir tema del día ─────────────────────────────────────
topic = TOPICS[datetime.date.today().weekday() % len(TOPICS)]

# ── 2. Generar texto con Groq ──────────────────────────────────
groq_client = Groq(api_key=GROQ_API_KEY)

prompt = f"""
Eres un experto en {topic}. Crea un post viral para LinkedIn con:
- Un título gancho de máximo 12 palabras (sin comillas)
- Una descripción atractiva de 150-200 palabras con emojis
- 5 hashtags relevantes

Responde EXACTAMENTE en este formato:
TITULO: [título aquí]
DESCRIPCION: [descripción aquí]
HASHTAGS: [#tag1 #tag2 #tag3 #tag4 #tag5]
PROMPT_IMAGEN: [descripción en inglés de una imagen profesional que ilustre el tema, estilo fotorrealista]
"""

response = groq_client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": prompt}]
)
text = response.choices[0].message.content

titulo      = re.search(r"TITULO:\s*(.+)",      text).group(1).strip()
descripcion = re.search(r"DESCRIPCION:\s*([\s\S]+?)(?=HASHTAGS:)", text).group(1).strip()
hashtags    = re.search(r"HASHTAGS:\s*(.+)",    text).group(1).strip()
img_prompt  = re.search(r"PROMPT_IMAGEN:\s*(.+)", text).group(1).strip()

post_text = f"{titulo}\n\n{descripcion}\n\n{hashtags}"
print("✅ Texto generado")

# ── 3. Generar imagen local con Pillow ─────────────────────────
img = Image.new("RGB", (1200, 628), color=(13, 110, 253))
draw = ImageDraw.Draw(img)

words = titulo.split()
lines, line = [], []
for word in words:
    line.append(word)
    if len(" ".join(line)) > 30:
        lines.append(" ".join(line[:-1]))
        line = [word]
lines.append(" ".join(line))

y = 628 // 2 - len(lines) * 40 // 2
for l in lines:
    draw.text((600, y), l, fill="white", anchor="mm")
    y += 50

buffer = io.BytesIO()
img.save(buffer, format="JPEG")
image_bytes = buffer.getvalue()
print("✅ Imagen generada en memoria")

# ── 4. Carga de Imagen vía API Moderna (/v2/images) ─────────────
# Se requiere obligatoriamente especificar la versión de la API en los headers globales
headers_modernos = {
    "Authorization": f"Bearer {LINKEDIN_TOKEN}",
    "Content-Type": "application/json",
    "LinkedIn-Version": "202401",  # Cabecera de versión mandatoria para /images y /posts
    "X-Restli-Protocol-Version": "2.0.0"
}

image_payload = {
    "initializeUploadRequest": {
        "owner": LINKEDIN_PERSON_URN
    }
}

print("Registrando imagen en la API moderna...")
reg = requests.post(
    "https://api.linkedin.com/v2/images?action=initializeUpload",
    json=image_payload, headers=headers_modernos
)

if reg.status_code != 200:
    print(f"❌ Error al inicializar imagen: {reg.text}")
reg.raise_for_status()

reg_data = reg.json()
upload_url = reg_data["value"]["uploadUrl"]
asset_urn  = reg_data["value"]["image"]

# Carga de los bytes binarios de la imagen
upload_headers = {
    "Authorization": f"Bearer {LINKEDIN_TOKEN}",
    "Content-Type": "image/jpeg"
}
up = requests.put(upload_url, data=image_bytes, headers=upload_headers)
up.raise_for_status()
print("✅ Imagen subida a LinkedIn")

# ── 5. Crear el Post usando /v2/posts (API Moderna Definitiva) ──
post_payload = {
    "author": LINKEDIN_PERSON_URN, # Mantenemos 'person' ya que la versión '202401' lo procesa de forma nativa
    "commentary": post_text,
    "visibility": "PUBLIC",
    "distribution": {
        "feedDistribution": "MAIN_FEED",
        "targetEntities": [],
        "thirdPartyDistributionChannels": []
    },
    "content": {
        "media": {
            "title": titulo,
            "id": asset_urn
        }
    },
    "lifecycleState": "PUBLISHED"
}

print("Publicando post final...")
post_resp = requests.post(
    "https://api.linkedin.com/v2/posts",
    json=post_payload, headers=headers_modernos
)

if post_resp.status_code not in [200, 201]:
    print(f"❌ Error al publicar: {post_resp.text}")
post_resp.raise_for_status()

print("✅ ¡Post publicado con éxito total en tu perfil de LinkedIn!")
