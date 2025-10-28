from interface import open_screen
import windows
import cables
from Kaspersky import flow_kaspersky
import itom
from Nomenclature import flow_nomenclature
import printer
import pandas as pd

if __name__ == "__main__":
    secretaria, chamado, arquivo, link_site, usuario_atribuido, log, logs = open_screen()

    if not arquivo:
        log("Automação cancelada.", "error")
        exit()

    try:
        df = pd.read_excel(arquivo)
    except Exception as e:
        log(f"Erro ao ler o arquivo Excel: {e}", "error")
        exit()

    # ⚠️ CORREÇÃO: Chama a função principal de cada fluxo
    if chamado == "WINDOWS":
        windows.flow_windows(df, secretaria, link_site, log)
    elif chamado == "CABOS":
        cables.flow_cables(df, secretaria, link_site, log)
    elif chamado == "ANTIVÍRUS":
        flow_kaspersky(df, secretaria, log)
    elif chamado == "ITOM":
        itom.flow_itom(df, secretaria, link_site, usuario_atribuido, log)
    elif chamado == "NOMENCLATURA":
        flow_nomenclature(df, secretaria, log)
    elif chamado == "IMPRESSORA":
        printer.flow_printer(df, secretaria, log)
        