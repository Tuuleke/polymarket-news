import os

# Runs before conftest.py imports the app: tests must not depend on a developer's .env.
os.environ["PMNEWS_ENV_FILE"] = ""
os.environ["SOURCES_ENABLED"] = ""  # no test may start a live fetch
os.environ["NEWS_ENABLED"] = "false"
