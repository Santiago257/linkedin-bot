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
Eres un expert en {topic}. Crea un post viral para LinkedIn con:
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

# ── 4. Subir imagen a LinkedIn (API Moderna) ───────────────────
# Usamos encabezados globales incluyendo la versión obligatoria de la API
headers = {
    "Authorization": f"Bearer {LINKEDIN_TOKEN}",
    "Content-Type": "application/json",
    "LinkedIn-Version": "202401" 
}

# Inicializar la carga de la imagen
image_init_payload = {
    "initializeUploadRequest": {
        "owner": LINKEDIN_PERSON_URN
    }
}

print("Iniciando carga de imagen...")
reg = requests.post(
    "https://api.linkedin.com/v2/images?action=initializeUpload",
    json=image_init_payload, headers=headers
)
reg.raise_for_status()
reg_data = reg.json()

upload_url = reg_data["value"]["uploadUrl"]
asset_urn  = reg_data["value"]["image"]  # Este es el ID único de la imagen generada (urn:li:image:...)

# Subir los bytes binarios de la imagen
upload_headers = {
    "Authorization": f"Bearer {LINKEDIN_TOKEN}",
    "Content-Type": "image/jpeg",
}
up = requests.put(upload_url, data=image_bytes, headers=upload_headers)
up.raise_for_status()
print("✅ Imagen subida a los servidores de LinkedIn")

# ── 5. Crear y publicar el Post (API Moderna) ──────────────────
post_payload = {
    "author": LINKEDIN_PERSON_URN,
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

print("Publicando post en tu muro...")
post_resp = requests.post(
    "https://api.linkedin.com/v2/posts",
    json=post_payload, headers=headers
)
post_resp.raise_for_status()
print("✅ ¡Post publicado con éxito en LinkedIn!")
