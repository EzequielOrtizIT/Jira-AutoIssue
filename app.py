import tkinter as tk
from tkinter import ttk

root = tk.Tk()                # crea la ventana
root.title("Jira Sandbox")    # título de la ventana
root.geometry("800x600")      # tamaño inicial (ancho x alto)

notebook = ttk.Notebook(root)

tab_entorno = ttk.Frame(notebook)
tab_ejecucion = ttk.Frame(notebook)

notebook.add(tab_entorno, text="Entorno Jira")
notebook.add(tab_ejecucion, text="Ejecución")

notebook.pack(expand=True, fill="both")

tk.Label(tab_entorno, text="Pestaña: Entorno Jira", bg="#d9d9d9").pack(fill="both", expand=True)
tk.Label(tab_ejecucion, text="Pestaña: Ejecución", bg="#cfcfcf").pack(fill="both", expand=True)

root.mainloop()               # arranca el loop de la app (queda abierta hasta cerrar)