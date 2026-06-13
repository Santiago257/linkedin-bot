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

# Asegurar que el formato base sea estrictamente "urn:li:person:..."
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

# ── 4. Registrar y Subir imagen (Método Assets Exitoso) ────────
headers = {
    "Authorization": f"Bearer {LINKEDIN_TOKEN}",
    "Content-Type": "application/json",
}

register_payload = {
    "registerUploadRequest": {
        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
        "owner": LINKEDIN_PERSON_URN,
        "serviceRelationships": [
            {
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent"
            }
        ]
    }
}

print("Registrando asset de imagen...")
reg = requests.post(
    "https://api.linkedin.com/v2/assets?action=registerUpload",
    json=register_payload, headers=headers
)
reg.raise_for_status()

reg_data = reg.json()
upload_url = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
asset_urn  = reg_data["value"]["asset"]

# Carga binaria de los bytes de la imagen
upload_headers = {
    "Authorization": f"Bearer {LINKEDIN_TOKEN}",
    "Content-Type": "image/jpeg"
}
up = requests.put(upload_url, data=image_bytes, headers=upload_headers)
up.raise_for_status()
print("✅ Imagen subida a LinkedIn")

# ── 5. Crear el Post vía ugcPosts (Modificado para IDs Modernos) ──
# Cambiamos la estructura para que acepte tu URN de tipo 'person' alfanumérico sin dar error 422 o 403
post_payload = {
    "author": LINKEDIN_PERSON_URN,
    "lifecycleState": "PUBLISHED",
    "specificContent": {
        "com.linkedin.ugc.ShareContent": {
            "shareCommentary": {"text": post_text},
            "shareMediaCategory": "IMAGE",
            "media": [{
                "status": "READY",
                "description": {"text": titulo},
                "media": asset_urn,
                "title": {"text": titulo}
            }]
        }
    },
    "visibility": {
        "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
    }
}

print("Publicando post...")
post_resp = requests.post(
    "https://api.linkedin.com/v2/ugcPosts",
    json=post_payload, headers=headers
)

if post_resp.status_code != 201:
    print(f"❌ Error al publicar: {post_resp.text}")
post_resp.raise_for_status()

print(f"✅ ¡Post publicado exitosamente! ID: {post_resp.headers.get('x-restli-id')}")
