import os, requests
from dotenv import load_dotenv

load_dotenv()  # lee .env en la carpeta del script

JIRA_URL   = os.getenv("JIRA_URL")           # https://ezequielortiz-jira.atlassian.net
JIRA_EMAIL = os.getenv("JIRA_EMAIL")         # tu correo Atlassian
JIRA_TOKEN = os.getenv("JIRA_API_TOKEN")     # token nuevo

r = requests.get(f"{JIRA_URL}/rest/api/3/myself",
                 auth=(JIRA_EMAIL, JIRA_TOKEN),
                 headers={"Accept":"application/json"})
print("Status:", r.status_code)
print(r.text[:300])
