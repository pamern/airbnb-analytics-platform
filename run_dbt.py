import os
import subprocess
from pathlib import Path

# Load .env manually if dotenv isn't installed
env_path = Path('.env')
if env_path.exists():
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip().strip("'").strip('"')

subprocess.run([
    "uv",
    "run",
    "dbt",
    "run",
    "--project-dir",
    "dbt",
    "--profiles-dir",
    "dbt",
    "--select",
    "gold_ai_qa_investment_recommendations",
])
