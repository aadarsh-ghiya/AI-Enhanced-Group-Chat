import os
import httpx

LLM_API_BASE = os.getenv("LLM_API_BASE", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3:instruct")


async def generate_reply(user_input: str, username: str, history=None) -> str:
    history = history or []

    messages = []

    # Add conversation history
    for msg in history:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # Add current message
    messages.append({
        "role": "user",
        "content": user_input
    })

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{LLM_API_BASE}/chat/completions",
                json={
                    "model": LLM_MODEL,
                    "messages": messages,
                    "temperature": 0.7
                }
            )

        data = response.json()

        return data["choices"][0]["message"]["content"]

    except Exception as e:
        print("LLM ERROR:", e)
        return "Sorry, I couldn't generate a response right now."