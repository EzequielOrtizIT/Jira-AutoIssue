import tkinter as tk
from tkinter import ttk, messagebox
import os, json, random, requests, sys # Importaciones necesarias para la API
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
        master.geometry("800x650")

        # 1. Cargar las plantillas al inicio de la app
        self.templates = self.load_templates()
        self.current_template = None

        # 2. Variables de control de la UI
        self.project_key = tk.StringVar()
        self.issue_type = tk.StringVar(value="")
        self.priority_level = tk.StringVar(value="Medium")
        self.summary_text = tk.StringVar()
        self.status_message = tk.StringVar(value="Listo para generar y cargar issue.")
        
        self.issue_types_map = {} # Diccionario para guardar Nombre -> ID
        self.available_issue_types = [] # Lista de nombres disponibles
        self.available_priorities = ["Highest", "High", "Medium", "Low", "Lowest"]

        self.load_jira_metadata()

        # 3. Construir la interfaz
        self.create_widgets()

    def load_jira_metadata(self):
        """Carga dinámicamente los tipos de issue y sus IDs desde la API de Jira."""
        
        project_key = self.project_key.get() or "AUT"
        
        # URL de la API de Metadatos: pedimos todos los tipos de issue para el proyecto AUT
        url = f"{JIRA_URL}/rest/api/3/issue/createmeta?projectKeys={project_key}&expand=projects.issuetypes"

        self.available_issue_types = [] # Lista de nombres visibles en la UI
        self.issue_types_map = {}      # Mapeo de Nombre -> ID
        self.available_priorities = ["Highest", "High", "Medium", "Low", "Lowest"] # Mantenemos esto estático por simplicidad

        try:
            resp = requests.get(
                url,
                auth=(JIRA_EMAIL, JIRA_API_TOKEN),
                headers={ "Accept":"application/json" }
            )
            resp.raise_for_status()
            metadata = resp.json()

            # 1. Verificar si el proyecto existe y procesar la respuesta
            if not metadata.get('projects'):
                # Usamos messagebox para informar al usuario sobre el problema
                messagebox.showerror("Error de Metadatos", "Proyecto no encontrado o sin permisos.")
                return 

            project_meta = metadata['projects'][0] # Tomamos el primer proyecto (AUT)
            
            # 2. Llenar el mapeo Nombre -> ID
            for issue_type in project_meta.get('issuetypes', []):
                name = issue_type['name']
                id_value = issue_type['id']
                
                self.available_issue_types.append(name)
                self.issue_types_map[name] = id_value
            
            # 3. Mostrar estado de éxito (opcional)
            print(f"Metadatos cargados: {len(self.available_issue_types)} tipos de issue encontrados.")

        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error de Conexión", f"No se pudo cargar metadatos de Jira. Revise URL/Token. Detalles: {e}")


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
        # Se asegura de que la estructura para Jira sea la correcta (content/type:paragraph)
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

    def create_issue(self, summary_text, description_text, tpl):
        """Envía la solicitud POST a la API de Jira."""
        assignee_data = tpl.get("assignee", {})

        current_priority = self.priority_level.get()
        current_issue_type_name = self.issue_type.get()
        issue_type_id = self.issue_types_map.get(current_issue_type_name)

        if not issue_type_id:
             messagebox.showerror("Error", f"Tipo '{current_issue_type_name}' no encontrado en metadatos.")
             return {"success": False, "error": "Tipo de Issue no mapeado", "details": ""}
        
        
        payload = {
            "fields": {
                "project":{ "key": self.project_key.get() or "AUT" },
                "issuetype":{ "id": issue_type_id },
                "summary": summary_text, # <-- USA EL RESUMEN EDITADO
                "description": self.make_atlassian_doc(description_text), # <-- USA LA DESCRIPCIÓN EDITADA
                "priority": { "name": current_priority },
                "labels": tpl.get("labels", []), 
                # "duedate":tpl.get("duedate"),
            }
        }

        # Añade el assignee solo si está presente para evitar errores con campos vacíos
        if assignee_data:
             payload["fields"]["assignee"] = assignee_data

        try:
            resp = requests.post(
                f"{JIRA_URL}/rest/api/3/issue",
                auth=(JIRA_EMAIL, JIRA_API_TOKEN),
                headers={ "Accept":"application/json", "Content-Type":"application/json" },
                json=payload
            )
            resp.raise_for_status() # Lanza excepción para códigos de error (4xx o 5xx)
            return {"success": True, "key": resp.json()["key"]}
        
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Error de API: {e.response.status_code if e.response is not None else 'N/A'}", "details": e.response.text if e.response is not None else str(e)}
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
        self.issue_type.set(tpl.get("issuetype", ""))
        self.priority_level.set(tpl.get("priority_name", "Medium")) # Usamos el nombre de la prioridad
        
        # 2. Actualizar etiquetas y prioridad
        priority_name = tpl.get("priority_name", "Medium")
        self.priority_level.set(priority_name)
        self.labels_label.config(text=f"{', '.join(tpl.get('labels', []))}")
        
        # 3. Actualizar la descripción (campo Text requiere desbloqueo temporal)
        description_content = tpl.get("description", "Descripción no disponible en la plantilla. Por favor, edita este campo.")
        self.description_text.config(state=tk.NORMAL)
        self.description_text.delete("1.0", tk.END)
        self.description_text.insert(tk.END, description_content)
        
        
        self.status_message.set("Plantilla cargada. Lista para la subida.")

    def handle_create_issue(self):
        """Maneja el clic del botón para crear el issue."""
        if not self.current_template:
            self.status_message.set("Error: Primero genera una tarea aleatoria.")
            return
        
        # 1. Recuperar el texto editado del widget Text y Summary
        edited_description = self.description_text.get("1.0", tk.END).strip()
        current_summary = self.summary_text.get().strip()


        # 1. Validar la configuración mínima
        if not JIRA_URL or not JIRA_API_TOKEN:
            messagebox.showerror("Error de Configuración", "Las credenciales JIRA_URL/JIRA_API_TOKEN no están configuradas en el .env.")
            self.status_message.set("Error de configuración (.env).")
            return
            
        self.status_label.config(foreground="orange")
        self.status_message.set("Enviando issue a Jira...")
        self.master.update_idletasks() # Forzar la actualización de la UI
        
        # 2. Llamar a la función de la API
        response = self.create_issue(current_summary, edited_description, self.current_template)

        # 3. Mostrar el resultado
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

    def load_jira_metadata(self):
        """Carga dinámicamente los tipos de issue y prioridades disponibles para el proyecto."""
        
        project_key = self.project_key.get() or "AUT"
        
        # 1. URL de la API de Metadatos
        url = f"{JIRA_URL}/rest/api/3/issue/createmeta?projectKeys={project_key}&expand=projects.issuetypes.fields"

        try:
            resp = requests.get(
                url,
                auth=(JIRA_EMAIL, JIRA_API_TOKEN),
                headers={ "Accept":"application/json" }
            )
            resp.raise_for_status()
            metadata = resp.json()

            # 2. Procesar la respuesta
            if not metadata.get('projects'):
                messagebox.showerror("Error de Metadatos", "Proyecto no encontrado o sin permisos.")
                return False

            project_meta = metadata['projects'][0]
            
            # Obtener Tipos de Issue (Nombre y ID)
            issue_types_map = {
                item['name']: item['id'] for item in project_meta.get('issuetypes', [])
            }
            self.available_issue_types = list(issue_types_map.keys())
            self.issue_types_map = issue_types_map # Guardamos el mapeo Nombre -> ID

            # Nota: La API de 'createmeta' no siempre devuelve las prioridades fácilmente, 
            # pero asumimos que son estándar o que podemos cargarlas de forma separada.
            
            return True

        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error de Conexión", f"No se pudo cargar metadatos de Jira: {e}")
            return False


    # --- DISEÑO DE LA INTERFAZ (Tkinter) ---

    def create_widgets(self):
        # Primero se crea el menú antes que el resto de los widgets
        self.setup_menu() 
        
        # Frame Principal (Contenedor)
        main_frame = ttk.Frame(self.master, padding="10")
        main_frame.pack(fill="both", expand=True)

        # 1. Configuración Fija (Mostrar de dónde vienen los datos)
        config_frame = ttk.LabelFrame(main_frame, text="Configuración (Desde .env)", padding="10")
        config_frame.pack(fill="x", pady=5)
        ttk.Label(config_frame, text=f"URL: {JIRA_URL}", anchor="w").pack(fill="x")
        ttk.Label(config_frame, text=f"Usuario: {JIRA_EMAIL}", anchor="w").pack(fill="x")
        
        # 2. Controles Dinámicos (Dropdowns y Proyecto)
        control_frame = ttk.LabelFrame(main_frame, text="Controles de Issue", padding="10")
        control_frame.pack(fill="x", pady=5)
        
        # 3. Detalle de la Tarea (El Frame de la Descripción y Resumen)
        # ESTA ES LA ÚNICA VEZ QUE DEBE DEFINIRSE fields_frame
        fields_frame = ttk.LabelFrame(main_frame, text="Detalle de la Tarea Generada", padding="10")
        fields_frame.pack(fill="both", expand=True, pady=5)

        ttk.Label(control_frame, text="Proyecto (Key):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(control_frame, textvariable=self.project_key, width=10).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.project_key.set("AUT") # Valor por defecto


        ttk.Label(control_frame, text="Tipo de Issue:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.issue_type_combobox = ttk.Combobox(
             control_frame, 
             textvariable=self.issue_type,
             values=self.available_issue_types, # ¡USA LA LISTA DINÁMICA!
             state="readonly",
             width=40
         )
        self.issue_type_combobox.grid(row=0, column=3, padx=5, pady=5, sticky="w")
       


        # Botón de Generar Tarea
        ttk.Button(control_frame, text="Generar Tarea Aleatoria", command=self.load_random_template).grid(row=0, column=4, padx=15, pady=5, sticky="w")
        
        # 3. Campos de Issue (Mostrar plantilla)
        fields_frame = ttk.LabelFrame(main_frame, text="Detalle de la Tarea Generada", padding="10")
        fields_frame.pack(fill="both", expand=True, pady=5)
        
        # Summary (Resumen)
        ttk.Label(fields_frame, text="Resumen:", font=('Arial', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.summary_entry = ttk.Entry(fields_frame, textvariable=self.summary_text, width=80)
        self.summary_entry.grid(row=0, column=1, columnspan=4, padx=5, pady=5, sticky="ew")

        # Prioridad (Combobox, asumiendo que lo quieres en fields_frame, aunque control_frame es mejor)
        # ¡IMPORTANTE! Las filas de grid deben ser consistentes. 
        ttk.Label(fields_frame, text="Prioridad:", font=('Arial', 10, 'bold')).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        priorities = ["Highest", "High", "Medium", "Low", "Lowest"]
        self.priority_combobox = ttk.Combobox(
            fields_frame,
            textvariable=self.priority_level, 
            values=priorities,
            state="readonly",
            width=20
        )
        self.priority_combobox.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # Etiquetas (Labels)
        ttk.Label(fields_frame, text="Etiquetas (Labels):", font=('Arial', 10, 'bold')).grid(row=2, column=0, padx=5, pady=5, sticky="nw")
        self.labels_label = ttk.Label(fields_frame, text="", wraplength=600)
        self.labels_label.grid(row=2, column=1, padx=5, pady=5, sticky="w") # Usando la misma fila de grid
        
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
        
    def setup_menu(self):
        """Configura la barra de menú superior."""
        
        # 1. Crear la barra principal y asignarla a la ventana
        self.menu_bar = tk.Menu(self.master)
        self.master.config(menu=self.menu_bar)

        # 2. Crear los submenús
        self.config_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.help_menu = tk.Menu(self.menu_bar, tearoff=0)

        # 3. Asignar submenús a la barra principal
        self.menu_bar.add_cascade(label="Configuración", menu=self.config_menu)
        self.menu_bar.add_cascade(label="Ayuda", menu=self.help_menu)

        # 4. Añadir ítems y comandos (el comando llama a un método de la clase)
        self.config_menu.add_command(label="Credenciales Jira", command=self.open_config_window)
        self.config_menu.add_command(label="Opciones de Tareas", command=self.open_task_options)
        
        self.help_menu.add_command(label="Acerca de...", command=lambda: messagebox.showinfo("Acerca de", "Jira Issue Loader by Ezequiel Ortiz"))


    def open_config_window(self):
        """Este método manejará la nueva ventana de configuración."""
        # Obtiene los valores actuales (globales) de las constantes
        current_url = JIRA_URL
        current_email = JIRA_EMAIL
        current_token = JIRA_API_TOKEN  # No lo mostramos por seguridad, pero pasamos la constante si existe

        # 1. Chequea si ya existe una ventana de configuración abierta
        if hasattr(self, 'config_window') and self.config_window.winfo_exists():
            self.config_window.lift() # Si existe, tráela al frente
            return
            
        # 2. Crea la nueva ventana secundaria (Toplevel)
        self.config_window = ConfigWindow(self.master, current_url, current_email, current_token)


    def open_task_options(self):
        """Este método manejará la configuración de proyectos o tipos de issues."""
        messagebox.showinfo("Opciones", "Configurando proyectos y tipos de issue...")


    def restart_application(self):
        """Cierra la app actual y la reinicia ejecutando el script de nuevo."""
        
        # 1. Mensaje de advertencia
        if not messagebox.askyesno("Reiniciar", "¿Estás seguro de que quieres reiniciar la aplicación? Se perderán los datos no guardados."):
            return

        # 2. Cargar las nuevas variables del .env en el entorno de Python actual
        load_dotenv(override=True)

        # 3. Cerrar la ventana principal
        self.master.destroy() 
        
        # 3. Ejecutar el script nuevamente en un nuevo proceso de Python
        # sys.executable es la ruta al intérprete Python actual (dentro del venv)
        # sys.argv es la lista de argumentos pasados al script (el nombre del script, ej: ['app.py'])
        os.execl(sys.executable, sys.executable, *sys.argv)


class ConfigWindow(tk.Toplevel):
    """Ventana secundaria para configurar las credenciales de la API de Jira."""
    def __init__(self, master, current_url, current_email, current_token):
        # Llama al constructor de la clase base Toplevel
        super().__init__(master)
        self.title("Configuración de Credenciales de Jira")
        self.transient(master) # Mantiene la ventana encima de la principal
        self.grab_set()        # Bloquea la interacción con la ventana principal

        # Variables para almacenar los datos
        self.url_var = tk.StringVar(value=current_url)
        self.email_var = tk.StringVar(value=current_email)
        self.token_var = tk.StringVar(value=current_token)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill="both", expand=True)

        # URL de Jira
        ttk.Label(main_frame, text="URL Base (ej. https://dominio.atlassian.net):").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        ttk.Entry(main_frame, textvariable=self.url_var, width=50).grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        # Email
        ttk.Label(main_frame, text="Email de la Cuenta (usuario):").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        ttk.Entry(main_frame, textvariable=self.email_var, width=50).grid(row=1, column=1, sticky="ew", pady=5, padx=5)

        # Token API
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
            
            # Informa al usuario y cierra
            messagebox.showinfo("Éxito", "Credenciales guardadas. Reinicia la aplicación para que surtan efecto.")
            self.destroy() # Cierra la ventana secundaria

            # 2. Pregunta si desea reiniciar
            if messagebox.askyesno("Éxito", "Credenciales guardadas. ¿Deseas reiniciar la aplicación ahora para que surtan efecto?"):
                # Aquí llamamos a la función de reinicio de la aplicación principal
                # Usamos self.master para acceder a la ventana principal, y luego a la instancia de JiraApp
                
                # Acceso a la instancia de JiraApp (asumiendo que 'master' es la raíz)
                # Necesitamos pasar la referencia de JiraApp a la ConfigWindow para que esto funcione. 
                # Simplificaremos el acceso:
                
                # ---- NUEVO LLAMADO AL REINICIO ----
                # Creamos una instancia temporal de la app para acceder al método (aunque no es la más limpia, es sencilla)
                # La forma más limpia es pasar la instancia de JiraApp al constructor de ConfigWindow.
                
                # Opción más simple y directa: Usar la función estática de os/sys (fuera de la clase)
                # Dado que la función de reinicio es simple, la pondremos como una función fuera de la clase.
                
                # --- VUELVE A LA JIRAAPP ---
                # Debemos asegurarnos de que el reinicio se llame desde la JiraApp
                self.master.winfo_toplevel()._app_instance.restart_application()
            
            # --- NOTA IMPORTANTE: Para que esto funcione, necesitamos un pequeño cambio en JiraApp.__init__ ---


        except Exception as e:
            messagebox.showerror("Error al Guardar", f"No se pudo escribir en el archivo .env: {e}")


# --- EJECUCIÓN ---
if __name__ == "__main__":
    root = tk.Tk()
    
    # Intenta aplicar un tema moderno de Tkinter para mejor apariencia en Windows/Mac
    try:
        root.tk.call('source', 'azure.tcl')
        root.tk.call("set_theme", "light")
    except tk.TclError:
        pass # Si falla, usa el tema clásico

    app = JiraApp(root)
    root._app_instance = app
    root.mainloop()