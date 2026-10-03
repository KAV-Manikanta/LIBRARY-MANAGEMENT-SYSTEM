import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "academic-library-secret-key-2026")
    
    # MySQL 8.0 configuration
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "library_management_db")
    
    # URL encoded password for safe connection URI
    SAFE_PASSWORD = quote_plus(DB_PASSWORD)
    
    # MySQL Primary Connection URI
    MYSQL_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{SAFE_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    
    # SQLite Fallback URI (ensures project can run and demonstrate instantly even before MySQL credentials are configured)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # In Vercel or serverless environments, the filesystem is read-only except /tmp
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        import shutil
        tmp_db = "/tmp/library_fallback.db"
        orig_db = os.path.join(BASE_DIR, 'library_fallback.db')
        if not os.path.exists(tmp_db) and os.path.exists(orig_db):
            try:
                shutil.copyfile(orig_db, tmp_db)
            except Exception:
                pass
        SQLITE_DATABASE_URI = f"sqlite:///{tmp_db}"
    else:
        SQLITE_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'library_fallback.db')}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FINE_PER_DAY = float(os.getenv("FINE_PER_DAY", "5.00")) # Rs 5.00 / day
    DEFAULT_LOAN_DAYS = int(os.getenv("DEFAULT_LOAN_DAYS", "14"))
