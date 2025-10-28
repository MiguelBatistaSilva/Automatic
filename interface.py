import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext
from ttkthemes import ThemedTk
from placeholder import create_input_line

def open_screen():

    # --- Janela principal ---
    root = ThemedTk(theme="breeze")
    root.title("AUTOMATIC")
    root.geometry("1350x800")
    root.resizable(False, False)

    # --- Variáveis ---
    secretaria = tk.StringVar()
    chamado = tk.StringVar()
    arquivo = tk.StringVar()
    logs = []
    
    # ⚠️ NOVAS VARIÁVEIS
    link_site = tk.StringVar()
    usuario_atribuido = tk.StringVar()
    
    # ⚠️ VALORES PADRÃO (Para facilitar o uso, você pode definir padrões)
    #link_site.set("https://cati.tjce.jus.br/assystweb/application.do")

    # --- Frame principal ---
    frame = ttk.Frame(root, padding=30)
    frame.pack(fill="both", expand=True)
    
    # --- Linhas de Configuração (Para manter organizado) ---
    current_row = 0

    # Configura a grade para que os campos ocupem toda a largura da coluna central
    frame.grid_columnconfigure(0, weight=1)

    # --- 1. Secretaria ---
    entry_secretaria, line_secretaria = create_input_line(
        frame, secretaria, "SECRETARIA", root
    )
    entry_secretaria.grid(row=current_row, column=0, pady=(15, 0), sticky="ew")
    current_row += 1
    line_secretaria.grid(row=current_row, column=0, sticky="ew", pady=(0, 25))
    current_row += 1

    # --- 2. Tipo de Chamado (Manter Combobox, mas ajustar margem) ---
    ttk.Label(
        frame,
        text="Selecione o fluxo de automação que será executado.",
        # Você pode usar fg='gray' se quiser que a cor seja diferente (depende do tema ttkthemes)
        anchor="w"  # Alinha o texto à esquerda (West)
    ).grid(row=current_row, column=0, sticky="w", padx=5, pady=(15, 1))
    current_row += 1

    opcoes = ["WINDOWS", "CABOS", "ANTIVÍRUS", "ITOM", "NOMENCLATURA", "IMPRESSORA"]

    combo = ttk.Combobox(frame, textvariable=chamado, values=opcoes, state="readonly", width=47)
    combo.current(0)

    combo.grid(row=current_row, column=0, pady=(2, 18), sticky="ew")
    current_row += 1

    # --- 3. Link do Site ---
    entry_link, line_link = create_input_line(
        frame, link_site, "LINK ASSYST", root
    )
    entry_link.grid(row=current_row, column=0, pady=(15, 0), sticky="ew")
    current_row += 1
    line_link.grid(row=current_row, column=0, sticky="ew")
    current_row += 1
    
    # --- 4. Usuário Atribuído ---
    entry_usuario, line_usuario = create_input_line(
        frame, usuario_atribuido, "USUÁRIO ATRIBUÍDO", root
    )
    entry_usuario.grid(row=current_row, column=0, pady=(15, 0), sticky="ew")
    current_row += 1
    line_usuario.grid(row=current_row, column=0, sticky="ew")
    current_row += 1
    
    # 5. Escolher Arquivo
    
    def escolher_arquivo():
        path = filedialog.askopenfilename(
            defaultextension=".xlsx",
            filetypes=[("Arquivos Excel", "*.xlsx"), ("Todos os arquivos", "*.*")]
        )
        if path:
            arquivo.set(path)
            log(f"Arquivo selecionado: {path}", tipo="info")

    frame_arquivo = ttk.Frame(frame) 
    frame_arquivo.grid(row=current_row, column=0, pady=15, sticky="ew")
    frame_arquivo.grid_columnconfigure(0, weight=1) 
    
    # Sub-campo (ainda com a linha simulada)
    entry_arquivo, line_arquivo = create_input_line(
        frame_arquivo, arquivo, "CAMINHO DO ARQUIVO", root
    )
    entry_arquivo.grid(row=0, column=0, sticky="ew", padx=(0, 5))
    line_arquivo.grid(row=1, column=0, sticky="ew", padx=(0, 5))
    
    # Configura o campo Arquivo para ser apenas leitura
    entry_arquivo.config(state="readonly")
    
    ttk.Button(frame_arquivo, text="...", command=escolher_arquivo, width=5).grid(row=0, column=1, sticky="w")
    current_row += 1

    # --- Frame Log ---
    ttk.Label(frame, text="Log de Execução:").grid(row=current_row, column=0, columnspan=3, pady=10, sticky="w")
    current_row += 1
    
    log_box = scrolledtext.ScrolledText(frame, width=100, height=15, state="disabled", wrap=tk.WORD)
    log_box.grid(row=current_row, column=0, columnspan=3, padx=10, sticky="nsew", pady=5)
    current_row += 1

    # --- Função de log ---
    def log(msg, tipo="info"):
        logs.append(msg)
        log_box.config(state="normal")
        if tipo == "error":
            log_box.insert(tk.END, msg + "\n", "error")
        elif tipo == "status":
            log_box.insert(tk.END, msg + "\n", "status")
        else:
            log_box.insert(tk.END, msg + "\n")
        log_box.see(tk.END)
        log_box.config(state="disabled")
        root.update_idletasks()

    log_box.tag_config("error", foreground="red")
    log_box.tag_config("status", foreground="blue")

    # --- Frame Botões ---
    botoes = ttk.Frame(frame)
    botoes.grid(row=current_row, column=0, columnspan=3, pady=20, sticky="ew")

    def confirmar():
        if not arquivo.get() or not secretaria.get() or not link_site.get() or not usuario_atribuido.get():
            log("Erro: Preencha todos os campos obrigatórios!", tipo="error")
            return

        log("Iniciando automação...", tipo="status")
        log(f"Secretaria: {secretaria.get()} | Chamado: {chamado.get()} | Usuário: {usuario_atribuido.get()}", tipo="status")
        root.quit()

    ttk.Button(botoes, text="START", command=confirmar).pack(side="left", padx=20, expand=True, fill="x")
    ttk.Button(botoes, text="CANCEL", command=root.destroy).pack(side="right", padx=20, expand=True, fill="x")

    root.mainloop()
    
    # ⚠️ RETORNO FINAL: Adicionando as novas variáveis
    return secretaria.get(), chamado.get(), arquivo.get(), link_site.get(), usuario_atribuido.get(), log, logs