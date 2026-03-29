import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


load_dotenv()


def get_database_url() -> str:
    explicit_url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URL")
    if explicit_url:
        return explicit_url

    user = os.getenv("DB_USER", "root")
    raw_password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "enc_chat_db")

    password = quote_plus(raw_password)
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"
