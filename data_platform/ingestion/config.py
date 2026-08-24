import os
from dotenv import load_dotenv

# Load env variables from root or parents
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "globalcart"),
    "user": os.getenv("DB_USER", "globalcart"),
    "password": os.getenv("DB_PASSWORD", "globalcart"),
}
