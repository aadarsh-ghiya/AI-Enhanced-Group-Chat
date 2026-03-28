import httpx

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3:instruct" 


async def generate_reply(user_input: str, username: str, history=None) -> str:
    history = history or []

    messages = []

    for msg in history:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", "")
        })

    messages.append({
        "role": "user",
        "content": user_input
    })

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                OLLAMA_URL,
                json={
                    "model": MODEL_NAME,
                    "messages": messages,
                    "stream": False
                }
            )

        print("OLLAMA RAW:", response.text)

        data = response.json()

        reply = data.get("message", {}).get("content")

        if not reply:
            print("Unexpected Ollama response:", data)
            return " No response from model"

        return reply.strip()

    except Exception as e:
        print("LLM ERROR:", str(e))
        return " Error generating response"