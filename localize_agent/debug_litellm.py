import os
import litellm
from dotenv import load_dotenv
load_dotenv()  # loads variables from .env into environment


print("GOOGLE_API_KEY present?:", bool(os.getenv("GOOGLE_API_KEY")))
print("GOOGLE_API_KEY (first 8 chars):", os.getenv("GOOGLE_API_KEY")[:8] if os.getenv("GOOGLE_API_KEY") else None)

litellm._turn_on_debug()

try:
    # call a simple model name just to test the request (we'll list real models next)
    print(litellm.completion(model="models/text-bison-001", prompt="Hello", max_tokens=5))
except Exception as e:
    print("CALL FAILED:", type(e), e)
