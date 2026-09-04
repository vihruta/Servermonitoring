import os
from dotenv import load_dotenv

load_dotenv()

value = os.getenv('TOKEN')

if value is None:
    raise RuntimeError("TOKEN is not set")

token: str = value