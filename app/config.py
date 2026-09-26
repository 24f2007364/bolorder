import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DB_PATH = Path(os.getenv('DATABASE_PATH', str(ROOT / 'app/data/bolorder.sqlite3')))
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH
DEMO_MODE = os.getenv('DEMO_MODE', 'false').lower() == 'true'
PUBLIC_DEPLOYMENT = os.getenv('PUBLIC_DEPLOYMENT', 'false').lower() == 'true'
APP_ACCESS_PASSWORD = os.getenv('APP_ACCESS_PASSWORD', '')
PUBLIC_ORIGIN = os.getenv('PUBLIC_ORIGIN', os.getenv('RENDER_EXTERNAL_URL', '')).rstrip('/')
