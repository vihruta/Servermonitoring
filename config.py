import os
from dotenv import load_dotenv

load_dotenv()

token_value = os.getenv('TOKEN')
allowed_user_raw = os.getenv('ALLOWED_USER')

if token_value is None:
    raise RuntimeError("TOKEN is not set")

if allowed_user_raw is not None:
    allowed_users = {
        int(user_id) for user_id in allowed_user_raw.split(',')
        if user_id
    }
else:
    raise RuntimeError('Allowed user is not set')

token: str = token_value