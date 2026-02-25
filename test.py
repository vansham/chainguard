import opengradient as og
import os
from dotenv import load_dotenv

load_dotenv()
client = og.Client(private_key=os.getenv("OG_PRIVATE_KEY"))

print("llm type:", type(client.llm))
print("llm.chat type:", type(client.llm.chat))

try:
    result = client.llm.chat(
        model="gpt-4o",
        messages=[{"role": "user", "content": "test"}]
    )
    print("SUCCESS!")
    print(type(result))
    print(result)
except Exception as e:
    print("Error:", e)
