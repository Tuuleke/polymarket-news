import os

# Runs before conftest.py imports the app: tests must not depend on a developer's .env.
os.environ["PMNEWS_ENV_FILE"] = ""
