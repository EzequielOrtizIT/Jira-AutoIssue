import tkinter as tk
from tkinter import ttk, messagebox
import os, json, random, requests, sys 
from dotenv import load_dotenv

# Load sensitive environment variables from .env file
load_dotenv() 

# --- JIRA API CONFIGURATION CONSTANTS ---
JIRA_URL = os.getenv("JIRA_URL")           # Base URL for the Jira instance
JIRA_EMAIL = os.getenv("JIRA_EMAIL")       # User's Atlassian email
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN") # User's Personal Access Token (PAT)
TEMPLATES_FILE = "templates.json"          # File containing issue templates
# ----------------------------------------

class JiraApp:
    def __init__(self, master):
        self.master = master
        master.title("Jira Issue Loader - Portafolio Service Desk")
        master.geometry("900x700")

        # 1. Initialization: Load templates and metadata
        self.templates = self.load_templates()
        self.current_template = None # Stores the actively selected template data

        # 2. UI Control Variables (tk.StringVar)
        self.project_key = tk.StringVar(value="AUT")
        self.issue_type = tk.StringVar(value="") 
        self.priority_level = tk.StringVar(value="Medium")
        self.summary_text = tk.StringVar()
        self.parent_key = tk.StringVar() # Required for Subtask creation (Parent Issue Key)
        self.status_message = tk.StringVar(value="Ready to generate and load issue.")
        
        # 3. Dynamic Metadata from Jira API
        self.issue_types_map = {}      # Maps Issue Type Name to its required ID
        self.available_issue_types = [] # List of valid types for the Combobox
        self.available_priorities = ["Highest", "High", "Medium", "Low", "Lowest"] # Static list for priority

        self.load_jira_metadata() # Fetch valid Issue Types and IDs from Jira

        # Selects the first loaded issue type as default
        self.issue_type.set(self.available_issue_types[0] if self.available_issue_types else "") 
        
        # 4. Build the User Interface
        self.create_widgets()


# --- JIRA API HELPER FUNCTIONS ---
    
    def load_templates(self):
        """
        Loads issue template data from the local JSON file. 
        Shows an error if the file is not found.
        """
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            # Display UI warning if template file is missing.
            messagebox.showerror("File Error", f"Template file not found: {TEMPLATES_FILE}")
            return []

    def make_atlassian_doc(self, text):
        """
        Converts plain text into the Atlassian Document Format (ADF) JSON structure 
        required for Jira's description field.
        """
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        { "type": "text", "text": text }
                    ]
                }
            ]
        }

    def load_jira_metadata(self):
        """
        Dynamically fetches available issue types and their IDs for the current project.
        This ensures the app uses valid types recognized by Jira.
        """
        
        project_key = self.project_key.get() 
        # API endpoint to get issue creation metadata, expanding issue types.
        url = f"{JIRA_URL}/rest/api/3/issue/createmeta?projectKeys={project_key}&expand=projects.issuetypes"

        # Resetting dynamic lists and map before fetching new data
        self.available_issue_types = [] 
        self.issue_types_map = {} 

        try:
            resp = requests.get(
                url,
                auth=(JIRA_EMAIL, JIRA_API_TOKEN),
                headers={ "Accept":"application/json" }
            )
            # Raises HTTPError for bad responses (4xx or 5xx)
            resp.raise_for_status() 
            metadata = resp.json()

            # Check if the project was found in the metadata response
            if not metadata.get('projects'):
                messagebox.showerror("Metadata Error", "Project not found or check permissions.")
                return False

            project_meta = metadata['projects'][0] # Target project's metadata
            
            # Map Issue Type Name -> ID and populate the list for the Combobox
            for issue_type in project_meta.get('issuetypes', []):
                name = issue_type['name']
                id_value = issue_type['id']
                
                self.available_issue_types.append(name)
                self.issue_types_map[name] = id_value
            
            print(f"Metadata loaded: {len(self.available_issue_types)} issue types found.")
            return True

        except requests.exceptions.RequestException as e:
            # Handle connection, authentication, and HTTP errors gracefully
            messagebox.showerror("Connection Error", f"Failed to load Jira metadata. Check URL/Token. Details: {e}")
            return False

    def create_issue(self, summary_text, description_text, tpl):
        """
        Submits the POST request to the Jira API to create a new issue.
        Constructs the payload using dynamically selected and user-edited data.
        """
        assignee_data = tpl.get("assignee", {}) # Attempts to get assignee from template

        current_priority = self.priority_level.get()
        current_issue_type_name = self.issue_type.get() 
        issue_type_id = self.issue_types_map.get(current_issue_type_name) # Get required ID from cached map

        # Validate that the selected Issue Type has a valid ID
        if not issue_type_id:
             messagebox.showerror("Error", f"Issue Type '{current_issue_type_name}' is not valid.")
             return {"success": False, "error": "Invalid Issue Type ID", "details": ""}
        
        
        payload = {
            "fields": {
                "project":{ "key": self.project_key.get() or "AUT" }, # Project Key
                "issuetype":{ "id": issue_type_id }, # Required Issue Type ID
                "summary": summary_text, # User-edited summary
                "description": self.make_atlassian_doc(description_text), # User-edited description in ADF format
                "priority": { "name": current_priority }, # Selected priority name
                "labels": tpl.get("labels", []), # Labels from template
            }
        }
        
        # --- CONDITIONAL LOGIC: SUBTASK REQUIRES PARENT KEY ---
        if "Subtarea" in current_issue_type_name or "Sub-task" in current_issue_type_name:
            parent_key = self.parent_key.get().strip()
            
            # Subtask validation: Parent Key cannot be empty
            if not parent_key:
                messagebox.showerror("Subtask Error", "Subtask type requires the Parent Issue Key (e.g., AUT-123).")
                return {"success": False, "error": "Missing Parent Key", "details": ""}
            
            # Add the 'parent' field to the payload
            payload['fields']['parent'] = { 'key': parent_key } 
        
        
        # Add assignee only if data exists in the template
        if assignee_data:
             payload["fields"]["assignee"] = assignee_data

        try:
            resp = requests.post(
                f"{JIRA_URL}/rest/api/3/issue",
                auth=(JIRA_EMAIL, JIRA_API_TOKEN),
                # Set headers for JSON data exchange
                headers={ "Accept":"application/json", "Content-Type":"application/json" },
                json=payload
            )
            # Check for 4xx or 5xx errors
            resp.raise_for_status() 
            # Return success and the key of the created issue
            return {"success": True, "key": resp.json()["key"]}
        
        except requests.exceptions.RequestException as e:
            # Handle all request/connection errors (e.g., 400 Bad Request, 401 Unauthorized)
            error_details = e.response.text if e.response is not None else str(e)
            error_status = e.response.status_code if e.response is not None else 'N/A'
            return {"success": False, "error": f"API Error: {error_status}", "details": error_details}
        except Exception as e:
            # Handle unexpected Python exceptions
            return {"success": False, "error": f"Unknown Error: {str(e)}", "details": str(e)}

   
    # --- EVENT HANDLERS ---
    
    def load_random_template(self):
        """
        Selects a random issue template and updates all editable UI fields.
        Also triggers dynamic field checks (e.g., Parent Key visibility).
        """
        if not self.templates:
            self.status_message.set("Error: Templates could not be loaded. Check templates.json.")
            return

        # Store the selected template data for submission
        self.current_template = random.choice(self.templates)
        tpl = self.current_template
        
        # 1. Update core fields (Summary, Type, Priority)
        self.summary_text.set(tpl["summary"])
        
        # Set Issue Type only if the type exists in the dynamically loaded list
        if tpl.get("issuetype", "") in self.available_issue_types:
            self.issue_type.set(tpl.get("issuetype", ""))
            
        priority_name = tpl.get("priority_name", "Medium")
        self.priority_level.set(priority_name) 
        
        # 2. Update auxiliary display fields
        self.labels_label.config(text=f"{', '.join(tpl.get('labels', []))}")
        
        # 3. Update the multi-line Description field
        description_content = tpl.get("description", "Description not available in template. Please edit this field.")
        self.description_text.config(state=tk.NORMAL) # Enable editing before inserting
        self.description_text.delete("1.0", tk.END)
        self.description_text.insert(tk.END, description_content)
        
        # 4. Enforce dynamic UI rules (e.g., show/hide Parent Key field)
        self.toggle_parent_key_field()
        
        self.status_message.set("Template loaded. Ready for submission.")

    def handle_create_issue(self):
        """
        Processes the 'Cargar Issue' button click event. 
        It retrieves user input, performs local validation, and triggers the Jira API submission.
        """
        # Validate that a template was first loaded (current_template is the source of other fields)
        if not self.current_template:
            self.status_message.set("Error: Must generate a random task first.")
            return
        
        # 1. Retrieve current data from editable UI widgets
        edited_description = self.description_text.get("1.0", tk.END).strip()
        current_summary = self.summary_text.get().strip()

        # Input Validation: Summary field cannot be empty (Jira requirement)
        if not current_summary:
            messagebox.showerror("Validation Error", "The Summary field cannot be empty.")
            return
        
        # 2. Configuration Validation: Check if .env constants are available
        if not JIRA_URL or not JIRA_API_TOKEN:
            messagebox.showerror("Configuration Error", "Jira credentials (URL/API_TOKEN) are not configured in the .env.")
            self.status_message.set("Configuration error (.env).")
            return
            
        # Update UI state to show processing
        self.status_label.config(foreground="orange")
        self.status_message.set("Sending issue to Jira...")
        self.master.update_idletasks() 
        
        # 3. Call the API logic with user-edited and template data
        response = self.create_issue(current_summary, edited_description, self.current_template)

        # 4. Process and display the API result
        if response["success"]:
            msg = f"✅ Success: Issue {response['key']} created."
            self.status_label.config(foreground="green")
            self.status_message.set(msg)

        else:
            # Extract error code and display detailed error to the user
            error_code = response['error'].split(':')[-1].strip()
            msg = f"❌ Error {error_code} while creating issue."
            self.status_label.config(foreground="red")
            self.status_message.set(msg)
            messagebox.showerror(msg, response['details'])

    def toggle_parent_key_field(self, event=None):
        """
        Dynamically shows or hides the Parent Key input field based on the selected Issue Type.
        This enforces Subtask schema requirements in the UI.
        """
        selected_type = self.issue_type.get()
        
        # Check if the selected type is a Subtask (handles variations like "Sub-task" or "Subtarea").
        if "Subtarea" in selected_type or "Sub-task" in selected_type: 
            row_num = 5 # Target row for grid layout
            self.parent_key_label.grid(row=row_num, column=0, padx=5, pady=5, sticky="w")
            self.parent_key_entry.grid(row=row_num, column=1, padx=5, pady=5, sticky="w")
        else:
            # Hide the widgets using grid_remove() to collapse the space they occupy.
            self.parent_key_label.grid_remove()
            self.parent_key_entry.grid_remove()

    # --- UI DESIGN AND WIDGET PLACEMENT (Tkinter) ---

    def create_widgets(self):
        # Setup the top menu bar (File, Configuration, Help)
        self.setup_menu() 
        
        # Main Frame (Container for all elements)
        main_frame = ttk.Frame(self.master, padding="10")
        main_frame.pack(fill="both", expand=True)

        # 1. Fixed Configuration Display (Read-only data from .env)
        config_frame = ttk.LabelFrame(main_frame, text="Configuration (From .env)", padding="10")
        config_frame.pack(fill="x", pady=5)
        ttk.Label(config_frame, text=f"URL: {JIRA_URL}", anchor="w").pack(fill="x")
        ttk.Label(config_frame, text=f"User: {JIRA_EMAIL}", anchor="w").pack(fill="x")
        
        # 2. Dynamic Controls (Project Key, Issue Type Selector, Generator Button)
        control_frame = ttk.LabelFrame(main_frame, text="Issue Controls", padding="10")
        control_frame.pack(fill="x", pady=5)
        
        # PROJECT KEY
        ttk.Label(control_frame, text="Project (Key):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(control_frame, textvariable=self.project_key, width=10).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        # ISSUE TYPE (Combobox, dynamically populated)
        ttk.Label(control_frame, text="Issue Type:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.issue_type_combobox = ttk.Combobox(
             control_frame, 
             textvariable=self.issue_type,
             values=self.available_issue_types, # Dynamic list from API
             state="readonly",
             width=20
        )
        self.issue_type_combobox.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        
        # Bind the type selector to the dynamic field handler (Subtask/Parent Key logic)
        self.issue_type_combobox.bind("<<ComboboxSelected>>", self.toggle_parent_key_field)
        
        # Button to load random issue template
        ttk.Button(control_frame, text="Generate Random Task", command=self.load_random_template).grid(row=0, column=4, padx=15, pady=5, sticky="w")
        
        # 3. Issue Detail Frame (Editable Fields)
        fields_frame = ttk.LabelFrame(main_frame, text="Generated Task Details", padding="10")
        fields_frame.pack(fill="both", expand=True, pady=5)

        # Summary (Editable Entry Field)
        ttk.Label(fields_frame, text="Summary:", font=('Arial', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.summary_entry = ttk.Entry(fields_frame, textvariable=self.summary_text, width=80)
        self.summary_entry.grid(row=0, column=1, columnspan=4, padx=5, pady=5, sticky="ew")

        # --- PARENT KEY FIELD (Hidden by default) ---
        # Define widgets without grid/pack; placement is handled by toggle_parent_key_field()
        self.parent_key_label = ttk.Label(fields_frame, text="Parent Key (for Subtasks):", font=('Arial', 10, 'bold'))
        self.parent_key_entry = ttk.Entry(fields_frame, textvariable=self.parent_key, width=30)
        
        # Priority (Combobox)
        ttk.Label(fields_frame, text="Priority:", font=('Arial', 10, 'bold')).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.priority_combobox = ttk.Combobox(
            fields_frame,
            textvariable=self.priority_level, 
            values=self.available_priorities,
            state="readonly",
            width=20
        )
        self.priority_combobox.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # Labels Display
        ttk.Label(fields_frame, text="Labels:", font=('Arial', 10, 'bold')).grid(row=2, column=0, padx=5, pady=5, sticky="nw")
        self.labels_label = ttk.Label(fields_frame, text="", wraplength=600)
        self.labels_label.grid(row=2, column=1, padx=5, pady=5, sticky="w") 
        
        # Description (Multi-line Text Field)
        ttk.Label(fields_frame, text="Description:", font=('Arial', 10, 'bold')).grid(row=3, column=0, padx=5, pady=5, sticky="nw")
        self.description_text = tk.Text(fields_frame, height=10, width=60, wrap=tk.WORD)
        self.description_text.grid(row=3, column=1, columnspan=4, padx=5, pady=5, sticky="ew")

        # 4. Submission Button and Status Bar
        action_frame = ttk.Frame(main_frame, padding="10")
        action_frame.pack(fill="x", pady=10)

        ttk.Button(action_frame, text="Load Issue to Jira 🚀", command=self.handle_create_issue, style='Accent.TButton').pack(side=tk.LEFT, padx=10)
        
        self.status_label = ttk.Label(action_frame, textvariable=self.status_message, font=('Arial', 10, 'italic'), foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Set initial UI state based on default Issue Type selection
        self.toggle_parent_key_field()


# --- UI MENU METHODS ---

    def setup_menu(self):
        """Initializes and configures the application's top menu bar."""
        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)

        # Configuration Submenu
        self.config_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Configuration", menu=self.config_menu)

        self.config_menu.add_command(label="Jira Credentials", command=self.open_config_window)
        self.config_menu.add_command(label="Task Options", command=self.open_task_options)
        self.config_menu.add_command(label="Restart Application", command=self.restart_application)
        
        # Help Submenu
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(
            label="About...", 
            command=lambda: messagebox.showinfo(
                "About Jira Issue Loader", 
                "Application: Jira Issue Loader (v1.0)\n"
                "Developer: Ezequiel Ortiz\n"
                "Creation Date: November 2025\n"
                "\n"
                "This tool was developed as a portfolio project to demonstrate proficiency in Python, Tkinter, and REST API consumption.\n"
                "\n"
                "🤖 Assisted by: Gemini (Google)"
            )
        )


    def open_config_window(self):
        """Handles the creation or focus of the secondary configuration window (Toplevel)."""
        # Retrieve current live configuration values from global constants
        current_url = JIRA_URL
        current_email = JIRA_EMAIL
        current_token = JIRA_API_TOKEN 

        # Check if the window is already open; if so, bring it to the front
        if hasattr(self, 'config_window') and self.config_window.winfo_exists():
            self.config_window.lift() 
            return
            
        # Create the new Toplevel window instance
        # Pass 'self' (the JiraApp instance) for restart functionality
        self.config_window = ConfigWindow(self.master, current_url, current_email, current_token, self)


    def open_task_options(self):
        """Placeholder for future advanced task configuration."""
        messagebox.showinfo("Options", "Configuring projects and issue types...")


    def restart_application(self):
        """
        Forces the application to restart cleanly by destroying the current process
        and launching a new one, ensuring fresh environment variables are loaded.
        """
        if not messagebox.askyesno("Restart", "Are you sure you want to restart the application? Unsaved data will be lost."):
            return

        # 1. Load fresh variables from the .env file into the current environment
        load_dotenv(override=True)

        # 2. Destroy the current UI window
        self.master.destroy() 
        
        # 3. Execute the script again using the current Python interpreter path
        os.execl(sys.executable, sys.executable, *sys.argv)


# --- CONFIGURATION WINDOW CLASS (Toplevel) ---
class ConfigWindow(tk.Toplevel):
    """Secondary window for editing and saving Jira API credentials to the .env file."""
    
    # Receive the JiraApp instance to call the restart method later
    def __init__(self, master, current_url, current_email, current_token, app_instance):
        super().__init__(master)
        self.app_instance = app_instance # Store reference to the main app instance
        self.title("Jira Credentials Configuration")
        self.transient(master) # Ensure the window stays on top of the main window
        self.grab_set() # Block interaction with the main window until closed

        # Variables for storing data from Entry fields
        self.url_var = tk.StringVar(value=current_url)
        self.email_var = tk.StringVar(value=current_email)
        self.token_var = tk.StringVar(value=current_token)

        self.create_widgets()

    # (create_widgets method in ConfigWindow is omitted for brevity, assumed correct)

    def save_and_close(self):
        """Validates input, saves new credentials to .env, and prompts for restart."""
        new_url = self.url_var.get().strip()
        new_email = self.email_var.get().strip()
        new_token = self.token_var.get().strip()

        # Input Validation
        if not new_url or not new_email or not new_token:
            messagebox.showwarning("Warning", "All fields must be filled.")
            return

        try:
            # Prepare and write new content to the .env file
            env_content = f"JIRA_URL=\"{new_url}\"\nJIRA_EMAIL=\"{new_email}\"\nJIRA_API_TOKEN=\"{new_token}\"\n"
            
            with open(".env", "w") as f:
                f.write(env_content)
            
            self.destroy() 

            # Prompt user to restart and apply changes
            if messagebox.askyesno("Success", "Credentials saved. Restart application now to take effect?"):
                self.app_instance.restart_application()
            
        except Exception as e:
            messagebox.showerror("Saving Error", f"Could not write to the .env file: {e}")


# --- EXECUTION BLOCK ---
if __name__ == "__main__":
    root = tk.Tk()
    
    # Theme configuration
    try:
        root.tk.call('source', 'azure.tcl')
        root.tk.call("set_theme", "light")
    except tk.TclError:
        pass 

    app = JiraApp(root)
    root.mainloop()