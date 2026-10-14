from config import GROQ_API_KEY, GROQ_CHAT_MODEL
from groq import Groq

print("Key loaded:", bool(GROQ_API_KEY), "| starts with:", GROQ_API_KEY[:4])
print("Model:", GROQ_CHAT_MODEL)

client = Groq(api_key=GROQ_API_KEY)
reply = client.chat.completions.create(
    model=GROQ_CHAT_MODEL,
    messages=[{"role": "user", "content": "Say hello in 3 words"}],
)
print("Groq replied:", reply.choices[0].message.content)