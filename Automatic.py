from interface import open_screen
import windows
import cables
import kaspersky
import itom
import nomenclature
import printer
import pandas as pd
import threading

# 1. FUNÇÃO DE EXECUÇÃO
def executar_fluxo(dados_interface):

    secretaria = dados_interface['secretaria']
    chamado = dados_interface['chamado']
    arquivo = dados_interface['arquivo']
    link_site = dados_interface['link_site']
    usuario_atribuido = dados_interface['usuario_atribuido']
    log = dados_interface['log']  # A função de log da GUI

    # 🛡️ BLOCO TRY-EXCEPT ENVOLVENDO TODA A LÓGICA
    try:
        # 2. Leitura do Excel
        log("Lendo arquivo Excel...", "status")
        try:
            df = pd.read_excel(arquivo)
        except Exception as e:
            # Captura erro de leitura do Excel (primeiro erro comum)
            raise ValueError(f"Erro ao ler o arquivo Excel: {e}")

            # 3. Execução do Fluxo Escolhido
        log(f"Iniciando a automação para o fluxo: {chamado}...", "status")

        if chamado == "WINDOWS":
            windows.flow_windows(df, secretaria, link_site, log)
        elif chamado == "CABOS":
            cables.flow_cables(df, secretaria, link_site, log)
        elif chamado == "ANTIVÍRUS":
            kaspersky.flow_kaspersky(df, secretaria, link_site, usuario_atribuido, log)
        elif chamado == "ITOM":
            itom.flow_itom(df, secretaria, link_site, usuario_atribuido, log)
        elif chamado == "NOMENCLATURA":
            nomenclature.flow_nomenclature(df, secretaria, link_site, usuario_atribuido, log)
        elif chamado == "IMPRESSORA":
            printer.flow_printer(df, secretaria, link_site, usuario_atribuido, log)
        else:
            raise ValueError(f"Erro: Fluxo de automação '{chamado}' não reconhecido.")

        log("✅ Automação concluída com sucesso!", "status")

    except Exception as e:
        # 4. CAPTURA E REGISTRA QUALQUER ERRO GERAL
        log(f"❌ A execução do fluxo FALHOU: {e}", "error")
        # O programa NÃO ENCERRA AQUI, apenas registra o erro e o mainloop da GUI continua rodando.


def iniciar_automacao_em_thread(dados_interface):
    """
    Inicia o processo de automação (executar_fluxo) em um thread separado.
    """

    # Adiciona uma mensagem de status enquanto o thread está sendo criado
    log = dados_interface['log']

    thread = threading.Thread(
        target=executar_fluxo,
        args=(dados_interface,)  # O argumento deve ser passado como uma tupla
    )

    thread.start()

if __name__ == "__main__":
    resultado_interface = open_screen(callback_executar=iniciar_automacao_em_thread)
        