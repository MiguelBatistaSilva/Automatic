import tkinter as tk

def create_input_line(parent_frame, textvariable, placeholder_text, root):
    """
    Cria um campo de entrada com placeholder e estilo de linha inferior.
    """
    
    # --- 1. Cria o campo Entry (tk.Entry para maior controle de estilo) ---
    entry_widget = tk.Entry(
        parent_frame, 
        textvariable=textvariable,
        font=('Helvetica', 13),  # Fonte para melhor leitura
        bd=0, # Remove a borda padrão
        highlightthickness=0, # Remove a borda de highlight
        relief='flat' # Deixa o fundo liso
    )
    
    # --- 2. Cria o Placeholder (reutilizando a lógica anterior) ---
    placeholder_color = 'grey'
    default_fg_color = entry_widget['foreground']

    def on_focus_in(event):
        if entry_widget.get() == placeholder_text:
            entry_widget.delete(0, tk.END)
            entry_widget.config(fg=default_fg_color)

    def on_focus_out(event):
        if not entry_widget.get():
            entry_widget.insert(0, placeholder_text)
            entry_widget.config(fg=placeholder_color)

    entry_widget.insert(0, placeholder_text)
    entry_widget.config(fg=placeholder_color)
    entry_widget.bind('<FocusIn>', on_focus_in)
    entry_widget.bind('<FocusOut>', on_focus_out)
    
    # --- 3. Cria a linha inferior (Frame fino) ---
    line_frame = tk.Frame(parent_frame, height=2, bg='#AAAAAA') # Cor cinza escuro
    
    # --- 4. Empacota e retorna os widgets ---
    return entry_widget, line_frame

def setup_placeholder(entry_widget, placeholder_text, root):
    """
    Configura um texto de placeholder em um widget Entry.
    O texto some ao ganhar foco e reaparece se o campo for deixado vazio.
    """
    
    # Define a cor do placeholder (cinza claro)
    placeholder_color = 'grey'
    # Define a cor do texto normal
    default_fg_color = entry_widget['foreground']

    def on_focus_in(event):
        if entry_widget.get() == placeholder_text:
            entry_widget.delete(0, tk.END)
            entry_widget.config(foreground=default_fg_color)

    def on_focus_out(event):
        if not entry_widget.get():
            entry_widget.insert(0, placeholder_text)
            entry_widget.config(foreground=placeholder_color)

    # 1. Configura o estado inicial
    entry_widget.insert(0, placeholder_text)
    entry_widget.config(foreground=placeholder_color)

    # 2. Binda os eventos
    entry_widget.bind('<FocusIn>', on_focus_in)
    entry_widget.bind('<FocusOut>', on_focus_out)
    
    # Garante que o foco inicial não esteja no primeiro campo
    root.focus_set()