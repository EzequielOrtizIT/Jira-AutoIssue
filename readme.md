# 🚀 Jira Issue Loader (Tkinter Automation Tool)

This project is a powerful Python application with a Graphical User Interface (GUI) built using **Tkinter**. It is designed to automate the process of creating Jira issues (tickets) by dynamically fetching project metadata and validating complex issue schemes before submission.

This tool demonstrates proficiency in **Python POO**, **Tkinter UI design**, **REST API integration**, and professional **Service Desk / DevOps automation**.

---

## ✨ Features Implemented

* **Dynamic Issue Type Loading:** The application connects to the Jira API (`/rest/api/3/issue/createmeta`) at startup to fetch the exact, valid Issue Types and their corresponding IDs for the target project (e.g., `AUT`).
* **Tkinter UI:** Provides a clean, functional interface for viewing, editing, and submitting ticket data.
* **Custom Credentials Management:** Allows users to configure their Jira URL, Email, and Personal Access Token (PAT) via a secure **Configuration Menu** (`Toplevel` window).
* **Automatic Restart:** Implemented a programmatic restart function to reload credentials immediately after saving the `.env` file, enhancing user experience.
* **Issue Data Pre-filling:** Loads issue data (Summary, Description, Priority, Labels) from a local `templates.json` file.
* **Dynamic Field Validation:** Conditionally displays the **Parent Key** field only when the selected Issue Type is a Subtask, preventing API errors (`Error 400`).
* **Robust API Handling:** Successfully manages and resolves common Jira API errors (e.g., `400 Bad Request`) caused by incompatible fields (`duedate`, `environment`, etc.).

---

## ⚙️ Installation and Setup

### Prerequisites

1.  **Python 3.x**
2.  **Jira Personal Access Token (PAT):** Required for API authentication.
3.  **Basic understanding of Git.**

### Step 1: Clone the Repository

Clone the project to your local machine:

```bash
git clone git@github.com:EzequielOrtizIT/Jira-AutoIssue.git
cd Jira-AutoIssue
Step 2: Set up Python Environment
Create and activate a virtual environment, then install the necessary dependencies:

Bash

python -m venv venv
.\venv\Scripts\activate # Use 'source venv/bin/activate' on Linux/macOS
pip install -r requirements.txt
Step 3: Configure Jira Credentials
⚠️ Security Note: The credentials file (.env) is excluded from Git for security reasons. You must create it manually.

Create a new file in the root directory named .env.

Copy the content below into the .env file, replacing the placeholder values with your actual data:

Fragmento de código

# JIRA API CREDENTIALS
JIRA_URL="https://[YOUR-DOMAIN].atlassian.net"
JIRA_EMAIL="your.atlassian.email@example.com"
JIRA_API_TOKEN="YOUR_PERSONAL_ACCESS_TOKEN"
(Alternatively, use the Configuration Menu in the running application to set these values.)

Step 4: Run the Application
Bash

python app.py
🔌 Connection Test Script (test_auth.py)
To quickly test your .env configuration outside of the GUI, you can run the provided simple script:

Python

import os, requests
from dotenv import load_dotenv

load_dotenv() 

JIRA_URL   = os.getenv("JIRA_URL") 
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_API_TOKEN") 

r = requests.get(f"{JIRA_URL}/rest/api/3/myself",
                 auth=(JIRA_EMAIL, JIRA_TOKEN),
                 headers={"Accept":"application/json"})
print("Status:", r.status_code)
print("User info (first 300 chars):", r.text[:300])

# Expected Output: Status: 200
🎯 Limitations & Future Vision
The application is currently focused on the Creation (C) stage of the Issue Lifecycle.

Current Limitations
Fixed Project Key: The default project key (AUT) is set in the application's code.

Read-Only Interaction: The application cannot yet Read, Update, or Delete existing issues (e.g., adding comments, changing the status from "To Do" to "In Progress," or closing a ticket).

Future Feature: AI-Generated Issues
The current issue pool is limited by the static templates.json file. A planned feature is to integrate with a Generative AI service (like Gemini) to dynamically create diverse and realistic support scenarios, providing infinite variability for testing.

Prompt Example for AI Generation:

If you wish to generate more scenarios for the templates.json file, use a prompt like this:

"Generate 5 Jira service desk ticket scenarios in JSON format. Each scenario must have 'summary', 'description', 'labels' (array of strings), 'priority_name' ('High', 'Medium', or 'Low'), and 'issuetype' ('Task', 'Incident', or 'Service request'). Focus the topics on IT Infrastructure, Networking, and Active Directory errors."

📝 Next Steps for Development
Implement Issue Interaction: Add a section to the UI to load an existing issue by key and perform actions (Add Comment, Change Status to 'In Progress').

Integrate AI Generation to replace templates.json reliance.