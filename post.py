import os
import re
import requests
from groq import Groq

# ── Configuración ──────────────────────────────────────────────
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
LINKEDIN_TOKEN       = os.environ["LINKEDIN_ACCESS_TOKEN"]
LINKEDIN_PERSON_URN  = os.environ["LINKEDIN_PERSON_URN"]

TOPICS = [
    "inteligencia artificial en negocios",
    "productividad con herramientas digitales",
    "liderazgo en la era tecnológica",
    "automatización de procesos",
    "tendencias tech 2025",
]

# ── 1. Elegir tema del día (rota por día de la semana) ─────────
import datetime
topic = TOPICS[datetime.date.today().weekday() % len(TOPICS)]

# ── 2. Generar texto con Gemini ────────────────────────────────
client = genai.Client(api_key=GEMINI_API_KEY)

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

# ── 3. Generar imagen con Pollinations.AI (gratis, sin API key) ─
import urllib.parse
encoded_prompt = urllib.parse.quote(img_prompt)
image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1200&height=628&nologo=true"

img_response = requests.get(image_url, timeout=60)
img_response.raise_for_status()
image_bytes = img_response.content
print("✅ Imagen generada")

# ── 4. Subir imagen a LinkedIn ──────────────────────────────────
headers = {
    "Authorization": f"Bearer {LINKEDIN_TOKEN}",
    "Content-Type": "application/json",
}

# 4a. Registrar el upload
register_payload = {
    "registerUploadRequest": {
        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
        "owner": LINKEDIN_PERSON_URN,
        "serviceRelationships": [{
            "relationshipType": "OWNER",
            "identifier": "urn:li:userGeneratedContent"
        }]
    }
}
reg = requests.post(
    "https://api.linkedin.com/v2/assets?action=registerUpload",
    json=register_payload, headers=headers
)
reg.raise_for_status()
reg_data = reg.json()

upload_url = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
asset_urn  = reg_data["value"]["asset"]

# 4b. Subir los bytes de la imagen
upload_headers = {
    "Authorization": f"Bearer {LINKEDIN_TOKEN}",
    "Content-Type": "image/jpeg",
}
up = requests.put(upload_url, data=image_bytes, headers=upload_headers)
up.raise_for_status()
print("✅ Imagen subida a LinkedIn")

# ── 5. Crear el post ───────────────────────────────────────────
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

post_resp = requests.post(
    "https://api.linkedin.com/v2/ugcPosts",
    json=post_payload, headers=headers
)
post_resp.raise_for_status()
print(f"✅ Post publicado: {post_resp.headers.get('x-restli-id')}")
