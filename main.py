from interface import open_screen
from Windows import flow_windows
from cables import flow_cables
from Kaspersky import flow_kaspersky
import itom
# import novoteste
from Nomenclature import flow_nomenclature
from Printer import flow_printer
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
        flow_windows(df, secretaria, log)
    elif chamado == "CABOS":
        flow_cables(df, secretaria, log)
    elif chamado == "ANTIVÍRUS":
        flow_kaspersky(df, secretaria, log)
    elif chamado == "ITOM":
        itom.flow_itom(df, secretaria, link_site, usuario_atribuido, log)
    elif chamado == "NOMENCLATURA":
        flow_nomenclature(df, secretaria, log)
    elif chamado == "IMPRESSORA":
        flow_printer(df, secretaria, log)
        