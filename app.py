import tkinter as tk
from tkinter import ttk, messagebox
import os, json, random, requests, sys 
from dotenv import load_dotenv

# Aseguramos que las credenciales se carguen al inicio del script
load_dotenv() 

# --- CONSTANTES DE CONFIGURACIÓN ---
JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
TEMPLATES_FILE = "templates.json"
# -----------------------------------

class JiraApp:
    def __init__(self, master):
        self.master = master
        master.title("Jira Issue Loader - Portafolio Service Desk")
        master.geometry("900x700")

        # 1. Cargar las plantillas al inicio de la app
        self.templates = self.load_templates()
        self.current_template = None

        # 2. Variables de control de la UI y Metadatos
        self.project_key = tk.StringVar(value="AUT")
        self.issue_type = tk.StringVar(value="") 
        self.priority_level = tk.StringVar(value="Medium")
        self.summary_text = tk.StringVar()
        self.parent_key = tk.StringVar() # NUEVA: Clave para la Subtarea
        self.status_message = tk.StringVar(value="Listo para generar y cargar issue.")
        
        self.issue_types_map = {} 
        self.available_issue_types = [] 
        self.available_priorities = ["Highest", "High", "Medium", "Low", "Lowest"]

        self.load_jira_metadata() # Carga los tipos de issue
        self.issue_type.set(self.available_issue_types[0] if self.available_issue_types else "") # Selecciona el primer tipo válido
        
        # 3. Construir la interfaz
        self.create_widgets()


    # --- LÓGICA MIGRADA DE auto_issue.py ---
    
    def load_templates(self):
        """Carga los datos de templates.json."""
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            messagebox.showerror("Error de Archivo", f"No se encontró el archivo: {TEMPLATES_FILE}")
            return []

    def make_atlassian_doc(self, text):
        """Convierte un string en un objeto Atlassian Document."""
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
        """Carga dinámicamente los tipos de issue y sus IDs desde la API de Jira."""
        
        project_key = self.project_key.get() 
        # URL de la API de Metadatos: pedimos todos los tipos de issue para el proyecto AUT
        url = f"{JIRA_URL}/rest/api/3/issue/createmeta?projectKeys={project_key}&expand=projects.issuetypes"

        self.available_issue_types = [] 
        self.issue_types_map = {} 

        try:
            resp = requests.get(
                url,
                auth=(JIRA_EMAIL, JIRA_API_TOKEN),
                headers={ "Accept":"application/json" }
            )
            resp.raise_for_status()
            metadata = resp.json()

            if not metadata.get('projects'):
                messagebox.showerror("Error de Metadatos", "Proyecto no encontrado o sin permisos.")
                return False

            project_meta = metadata['projects'][0]
            
            for issue_type in project_meta.get('issuetypes', []):
                name = issue_type['name']
                id_value = issue_type['id']
                self.available_issue_types.append(name)
                self.issue_types_map[name] = id_value
            
            print(f"Metadatos cargados: {len(self.available_issue_types)} tipos de issue encontrados.")
            return True

        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error de Conexión", f"No se pudo cargar metadatos de Jira. Revise URL/Token. Detalles: {e}")
            return False

    def create_issue(self, summary_text, description_text, tpl):
        """Envía la solicitud POST a la API de Jira."""
        assignee_data = tpl.get("assignee", {})

        current_priority = self.priority_level.get()
        current_issue_type_name = self.issue_type.get() # <--- ¡AQUÍ SE LEE EL COMBOBOX!
        issue_type_id = self.issue_types_map.get(current_issue_type_name)

        if not issue_type_id:
             messagebox.showerror("Error", f"Tipo '{current_issue_type_name}' no válido.")
             return {"success": False, "error": "Tipo de Issue no mapeado", "details": ""}
        
        
        payload = {
            "fields": {
                "project":{ "key": self.project_key.get() or "AUT" },
                "issuetype":{ "id": issue_type_id },
                "summary": summary_text, 
                "description": self.make_atlassian_doc(description_text), 
                "priority": { "name": current_priority },
                "labels": tpl.get("labels", []), 
            }
        }
        
        # --- LÓGICA CONDICIONAL: SUBTAREA REQUIERE CLAVE PADRE ---
        if "Subtarea" in current_issue_type_name or "Sub-task" in current_issue_type_name:
            parent_key = self.parent_key.get().strip()
            
            if not parent_key:
                messagebox.showerror("Error de Subtarea", "El tipo de issue Subtarea requiere la clave del Issue Padre (ej. AUT-123).")
                return {"success": False, "error": "Falta Clave Padre", "details": ""}
            
            # Añadir el campo 'parent' al payload
            payload['fields']['parent'] = { 'key': parent_key } 
        
        
        if assignee_data:
             payload["fields"]["assignee"] = assignee_data

        try:
            resp = requests.post(
                f"{JIRA_URL}/rest/api/3/issue",
                auth=(JIRA_EMAIL, JIRA_API_TOKEN),
                headers={ "Accept":"application/json", "Content-Type":"application/json" },
                json=payload
            )
            resp.raise_for_status() 
            return {"success": True, "key": resp.json()["key"]}
        
        except requests.exceptions.RequestException as e:
            error_details = e.response.text if e.response is not None else str(e)
            error_status = e.response.status_code if e.response is not None else 'N/A'
            return {"success": False, "error": f"Error de API: {error_status}", "details": error_details}
        except Exception as e:
            return {"success": False, "error": f"Error desconocido: {str(e)}", "details": str(e)}


    # --- MANEJADORES DE EVENTOS ---
    
    def load_random_template(self):
        """Selecciona una plantilla aleatoria y actualiza la UI."""
        if not self.templates:
            self.status_message.set("Error: No se cargaron plantillas. Revisa templates.json.")
            return

        self.current_template = random.choice(self.templates)
        tpl = self.current_template
        
        # 1. Actualizar campos de texto
        self.summary_text.set(tpl["summary"])
        # Intentamos setear el tipo de issue, si no existe lo dejamos como está
        if tpl.get("issuetype", "") in self.available_issue_types:
            self.issue_type.set(tpl.get("issuetype", ""))
        self.priority_level.set(tpl.get("priority_name", "Medium")) 
        
        # 2. Actualizar etiquetas y prioridad
        priority_name = tpl.get("priority_name", "Medium")
        self.priority_level.set(priority_name)
        self.labels_label.config(text=f"{', '.join(tpl.get('labels', []))}")
        
        # 3. Actualizar la descripción (campo Text requiere desbloqueo temporal)
        description_content = tpl.get("description", "Descripción no disponible en la plantilla. Por favor, edita este campo.")
        self.description_text.config(state=tk.NORMAL)
        self.description_text.delete("1.0", tk.END)
        self.description_text.insert(tk.END, description_content)
        
        # 4. Forzar la verificación dinámica por si el tipo de issue cambia
        self.toggle_parent_key_field()
        
        self.status_message.set("Plantilla cargada. Lista para la subida.")

    def handle_create_issue(self):
        """Maneja el clic del botón para crear el issue."""
        if not self.current_template:
            self.status_message.set("Error: Primero genera una tarea aleatoria.")
            return
        
        # 1. Recuperar el texto editado del widget Text y Summary
        edited_description = self.description_text.get("1.0", tk.END).strip()
        current_summary = self.summary_text.get().strip()

        # Validación mínima del resumen
        if not current_summary:
            messagebox.showerror("Error de Validación", "El resumen (Summary) no puede estar vacío.")
            return
        
        # 2. Validar la configuración mínima
        if not JIRA_URL or not JIRA_API_TOKEN:
            messagebox.showerror("Error de Configuración", "Las credenciales JIRA_URL/JIRA_API_TOKEN no están configuradas en el .env.")
            self.status_message.set("Error de configuración (.env).")
            return
            
        self.status_label.config(foreground="orange")
        self.status_message.set("Enviando issue a Jira...")
        self.master.update_idletasks() # Forzar la actualización de la UI
        
        # 3. Llamar a la función de la API
        response = self.create_issue(current_summary, edited_description, self.current_template)

        # 4. Mostrar el resultado
        if response["success"]:
            msg = f"✅ Éxito: Issue {response['key']} creado."
            self.status_label.config(foreground="green")
            self.status_message.set(msg)

        else:
            error_code = response['error'].split(':')[-1].strip()
            msg = f"❌ Error {error_code} al crear issue."
            self.status_label.config(foreground="red")
            self.status_message.set(msg)
            messagebox.showerror(msg, response['details'])

    # --- LÓGICA DINÁMICA DE LA UI ---

    def toggle_parent_key_field(self, event=None):
        """Muestra el campo Clave Padre si el tipo de issue es una Subtarea, y lo oculta si no lo es."""
        selected_type = self.issue_type.get()
        
        # Comprobar si el tipo de issue contiene "Subtarea", "Sub-task" o similar.
        if "Subtarea" in selected_type or "Sub-task" in selected_type: 
            row_num = 5 # Fila donde queremos que aparezca el campo
            self.parent_key_label.grid(row=row_num, column=0, padx=5, pady=5, sticky="w")
            self.parent_key_entry.grid(row=row_num, column=1, padx=5, pady=5, sticky="w")
        else:
            # OCULTAR: Usamos grid_remove para que el widget libere su espacio completamente.
            self.parent_key_label.grid_remove()
            self.parent_key_entry.grid_remove()

    # --- DISEÑO DE LA INTERFAZ (Tkinter) ---

    def create_widgets(self):
        self.setup_menu() 
        
        # Frame Principal (Contenedor)
        main_frame = ttk.Frame(self.master, padding="10")
        main_frame.pack(fill="both", expand=True)

        # 1. Configuración Fija 
        config_frame = ttk.LabelFrame(main_frame, text="Configuración (Desde .env)", padding="10")
        config_frame.pack(fill="x", pady=5)
        ttk.Label(config_frame, text=f"URL: {JIRA_URL}", anchor="w").pack(fill="x")
        ttk.Label(config_frame, text=f"Usuario: {JIRA_EMAIL}", anchor="w").pack(fill="x")
        
        # 2. Controles Dinámicos (Dropdowns y Proyecto)
        control_frame = ttk.LabelFrame(main_frame, text="Controles de Issue", padding="10")
        control_frame.pack(fill="x", pady=5)
        
        # PROYECTO
        ttk.Label(control_frame, text="Proyecto (Key):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(control_frame, textvariable=self.project_key, width=10).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        # TIPO DE ISSUE (Combobox)
        ttk.Label(control_frame, text="Tipo de Issue:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.issue_type_combobox = ttk.Combobox(
             control_frame, 
             textvariable=self.issue_type,
             values=self.available_issue_types, 
             state="readonly",
             width=20
        )
        self.issue_type_combobox.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        
        # ASIGNAR EVENTO DINÁMICO
        self.issue_type_combobox.bind("<<ComboboxSelected>>", self.toggle_parent_key_field)
        
        # Botón de Generar Tarea
        ttk.Button(control_frame, text="Generar Tarea Aleatoria", command=self.load_random_template).grid(row=0, column=4, padx=15, pady=5, sticky="w")
        
        # 3. Detalle de la Tarea (fields_frame)
        fields_frame = ttk.LabelFrame(main_frame, text="Detalle de la Tarea Generada", padding="10")
        fields_frame.pack(fill="both", expand=True, pady=5)

        # Summary (Resumen)
        ttk.Label(fields_frame, text="Resumen:", font=('Arial', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.summary_entry = ttk.Entry(fields_frame, textvariable=self.summary_text, width=80)
        self.summary_entry.grid(row=0, column=1, columnspan=4, padx=5, pady=5, sticky="ew")

        # --- CAMPO PADRE (INICIALIZACIÓN DE WIDGETS OCULTOS) ---
        # Definimos los widgets pero NO usamos .grid() o .pack() inicialmente.
        self.parent_key_label = ttk.Label(fields_frame, text="Clave Padre (Parent Key):", font=('Arial', 10, 'bold'))
        self.parent_key_entry = ttk.Entry(fields_frame, textvariable=self.parent_key, width=30)
        
        # Prioridad (Combobox)
        ttk.Label(fields_frame, text="Prioridad:", font=('Arial', 10, 'bold')).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.priority_combobox = ttk.Combobox(
            fields_frame,
            textvariable=self.priority_level, 
            values=self.available_priorities,
            state="readonly",
            width=20
        )
        self.priority_combobox.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # Etiquetas (Labels)
        ttk.Label(fields_frame, text="Etiquetas (Labels):", font=('Arial', 10, 'bold')).grid(row=2, column=0, padx=5, pady=5, sticky="nw")
        self.labels_label = ttk.Label(fields_frame, text="", wraplength=600)
        self.labels_label.grid(row=2, column=1, padx=5, pady=5, sticky="w") 
        
        # Description (Descripción)
        ttk.Label(fields_frame, text="Descripción:", font=('Arial', 10, 'bold')).grid(row=3, column=0, padx=5, pady=5, sticky="nw")
        self.description_text = tk.Text(fields_frame, height=10, width=60, wrap=tk.WORD)
        self.description_text.grid(row=3, column=1, columnspan=4, padx=5, pady=5, sticky="ew")

        # 4. Botón de Carga y Estado
        action_frame = ttk.Frame(main_frame, padding="10")
        action_frame.pack(fill="x", pady=10)

        ttk.Button(action_frame, text="Cargar Issue en Jira 🚀", command=self.handle_create_issue, style='Accent.TButton').pack(side=tk.LEFT, padx=10)
        
        self.status_label = ttk.Label(action_frame, textvariable=self.status_message, font=('Arial', 10, 'italic'), foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Aseguramos que el estado inicial sea correcto (mostrar/ocultar al iniciar)
        self.toggle_parent_key_field()

    # --- MÉTODOS DEL MENÚ ---

    def setup_menu(self):
        """Configura la barra de menú superior."""
        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)

        self.config_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Configuración", menu=self.config_menu)

        self.config_menu.add_command(label="Credenciales Jira", command=self.open_config_window)
        self.config_menu.add_command(label="Opciones de Tareas", command=self.open_task_options)
        self.config_menu.add_command(label="Reiniciar Aplicación", command=self.restart_application) # Nuevo ítem de menú
        
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Ayuda", menu=self.help_menu)
        self.help_menu.add_command(label="Acerca de...", command=lambda: messagebox.showinfo("Acerca de", "Jira Issue Loader by Ezequiel Ortiz"))

    def open_config_window(self):
        """Maneja la nueva ventana de configuración."""
        current_url = JIRA_URL
        current_email = JIRA_EMAIL
        current_token = JIRA_API_TOKEN 

        if hasattr(self, 'config_window') and self.config_window.winfo_exists():
            self.config_window.lift() 
            return
            
        # Pasamos la referencia a la instancia de JiraApp para el reinicio
        self.config_window = ConfigWindow(self.master, current_url, current_email, current_token, self)


    def open_task_options(self):
        """Maneja la configuración de proyectos o tipos de issues."""
        messagebox.showinfo("Opciones", "Configurando proyectos y tipos de issue...")

    def restart_application(self):
        """Cierra la app actual y la reinicia ejecutando el script de nuevo."""
        if not messagebox.askyesno("Reiniciar", "¿Estás seguro de que quieres reiniciar la aplicación? Se perderán los datos no guardados."):
            return

        # 1. Cargar las nuevas variables del .env en el entorno de Python actual
        load_dotenv(override=True)

        # 2. Cerrar la ventana principal
        self.master.destroy() 
        
        # 3. Ejecutar el script nuevamente en un nuevo proceso de Python
        os.execl(sys.executable, sys.executable, *sys.argv)

# --- CLASE DE CONFIGURACIÓN DE VENTANA (Secundaria) ---
class ConfigWindow(tk.Toplevel):
    """Ventana secundaria para configurar las credenciales de la API de Jira."""
    # Recibimos 'app_instance' para poder llamar al reinicio
    def __init__(self, master, current_url, current_email, current_token, app_instance):
        super().__init__(master)
        self.app_instance = app_instance # Guardamos la referencia de JiraApp
        self.title("Configuración de Credenciales de Jira")
        self.transient(master) 
        self.grab_set() 

        # Variables para almacenar los datos
        self.url_var = tk.StringVar(value=current_url)
        self.email_var = tk.StringVar(value=current_email)
        self.token_var = tk.StringVar(value=current_token)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill="both", expand=True)

        # ... (Widgets para URL, Email, Token) ...
        ttk.Label(main_frame, text="URL Base (ej. https://dominio.atlassian.net):").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        ttk.Entry(main_frame, textvariable=self.url_var, width=50).grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(main_frame, text="Email de la Cuenta (usuario):").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        ttk.Entry(main_frame, textvariable=self.email_var, width=50).grid(row=1, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(main_frame, text="Token API (PAT):").grid(row=2, column=0, sticky="w", pady=5, padx=5)
        ttk.Entry(main_frame, textvariable=self.token_var, show="*", width=50).grid(row=2, column=1, sticky="ew", pady=5, padx=5)
        
        # Botones de Acción
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=15)
        
        ttk.Button(button_frame, text="Guardar y Cerrar", command=self.save_and_close, style='Accent.TButton').pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancelar", command=self.destroy).pack(side=tk.LEFT, padx=10)

    def save_and_close(self):
        """Guarda las nuevas credenciales en el archivo .env."""
        new_url = self.url_var.get().strip()
        new_email = self.email_var.get().strip()
        new_token = self.token_var.get().strip()

        if not new_url or not new_email or not new_token:
            messagebox.showwarning("Advertencia", "Todos los campos deben estar llenos.")
            return

        try:
            # Recrea el contenido del archivo .env
            env_content = f"JIRA_URL=\"{new_url}\"\nJIRA_EMAIL=\"{new_email}\"\nJIRA_API_TOKEN=\"{new_token}\"\n"
            
            # Escribe el nuevo contenido en el archivo .env
            with open(".env", "w") as f:
                f.write(env_content)
            
            # Cierra la ventana secundaria
            self.destroy() 

            # Pregunta si desea reiniciar
            if messagebox.askyesno("Éxito", "Credenciales guardadas. ¿Deseas reiniciar la aplicación ahora para que surtan efecto?"):
                # Llamamos al método de la instancia de JiraApp que guardamos
                self.app_instance.restart_application()
            
        except Exception as e:
            messagebox.showerror("Error al Guardar", f"No se pudo escribir en el archivo .env: {e}")


# --- EJECUCIÓN ---
if __name__ == "__main__":
    root = tk.Tk()
    
    try:
        root.tk.call('source', 'azure.tcl')
        root.tk.call("set_theme", "light")
    except tk.TclError:
        pass 

    app = JiraApp(root)
    root.mainloop()