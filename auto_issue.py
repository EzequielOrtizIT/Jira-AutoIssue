import os, json, random, requests
from dotenv import load_dotenv
load_dotenv()


# ——— CONFIGURA ESTO ———
JIRA_URL       = os.getenv("JIRA_URL")
JIRA_EMAIL     = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
PROJECT_KEY    = "AUT"
ISSUE_TYPE     = "Task"
INTERVAL_SEC   = 60
TEMPLATES_FILE = "templates.json"
# ——————————————

def pick_template():
    with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
        templates = json.load(f)
    return random.choice(templates)

def make_atlassian_doc(text):
    """
    Convierte un string en un objeto Atlassian Document con un único párrafo.
    """
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    { "type": "text", "text": line }
                    for line in text.split("\n")
                ]
            }
        ]
    }

def create_issue(tpl):
    payload = {
        "fields": {
            "project":   { "key": PROJECT_KEY },
            "issuetype": { "name": ISSUE_TYPE },
            "summary":   tpl["summary"],
            "description": make_atlassian_doc(tpl["description"]),
            "priority":  { "id": tpl.get("priority", "3") },
            "labels":    tpl.get("labels", []), 
            "duedate":    tpl["duedate"],
        }
    }

    resp = requests.post(
        f"{JIRA_URL}/rest/api/3/issue",
        auth=(JIRA_EMAIL, JIRA_API_TOKEN),
        headers={ "Accept":"application/json", "Content-Type":"application/json" },
        json=payload
    )
    return resp

if __name__ == "__main__":
    import time
    print("Iniciando generador automático de incidencias desde plantillas…")
    while True:
        tpl = pick_template()
        r = create_issue(tpl)
        if r.status_code == 201:
            key = r.json()["key"]
            print(f"[+] Issue creado → {key}: {tpl['summary']}")
        else:
            print(f"[!] Error {r.status_code} → {r.text}")
        time.sleep(INTERVAL_SEC)
