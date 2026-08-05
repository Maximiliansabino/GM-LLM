import requests, json

BASE_URL = "http://26.12.169.161:1234"
API_KEY  = "sk-lm-3BmdHS1J:XkxtMziszhNEHEFi8iv3"
MODELO   = "qwen3.5-27b-claude-4.6-opus-reasoning-distilled"

headers = {
    "Authorization": f"Bearer {API_KEY.strip()}",
    "Content-Type" : "application/json",
}

# 1. Lista modelos — mostra resposta completa
print("GET /api/v1/models...")
r = requests.get(f"{BASE_URL}/api/v1/models", headers=headers, timeout=10)
print(f"Status: {r.status_code}")
print(f"Resposta completa: {json.dumps(r.json(), indent=2)[:500]}")

# 2. Chat — timeout de 3 minutos para modelo 27B
print(f"\nPOST /api/v1/chat com {MODELO}...")
print("(aguardando resposta do modelo 27B — pode demorar 1-2 min)...")
payload = {
    "model"            : MODELO,
    "input"            : "Responda apenas: OK",
    "system_prompt"    : "Seja muito breve.",
    "max_output_tokens": 10,
    "temperature"      : 0.1,
    "stream"           : False,
}
try:
    r = requests.post(f"{BASE_URL}/api/v1/chat",
                      headers=headers, json=payload, timeout=180)
    print(f"Status: {r.status_code}")
    data = r.json()
    if "error" in data:
        print(f"ERRO: {data['error']}")
    else:
        print(f"Resposta completa: {json.dumps(data, indent=2)[:600]}")
except requests.Timeout:
    print("TIMEOUT — modelo demorou mais de 3 minutos")
except Exception as e:
    print(f"ERRO: {e}")