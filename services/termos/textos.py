"""
services/termos/textos.py — O texto JURÍDICO das declarações (10/10).

Fica separado do layout de propósito: mudar a redação não mexe no documento.
Base: os termos em planilha do CATI, só com a gramática corrigida ("a serem",
"a chave", "em caso de"). Cada parágrafo é uma lista de trechos
(texto, negrito).
"""

Trecho = tuple[str, bool]


def declaracoes(backup: bool, varias: bool, trava: bool) -> list[list[Trecho]]:
    na_estacao = ("nas estações de trabalho identificadas neste termo" if varias
                  else "na estação de trabalho identificada neste termo")
    micro = "dos micros citados" if varias else "do micro citado"
    computador = "dos computadores" if varias else "do computador"

    if backup:
        primeira = [("DECLARO", True), (", pelo presente, que ", False),
                    ("FOI REALIZADO O BACKUP", True), (f" {na_estacao}.", False)]
    else:
        primeira = [("DECLARO", True), (", pelo presente, que ", False),
                    ("NÃO É NECESSÁRIO REALIZAR O BACKUP", True),
                    (f" {na_estacao}, não restando dados digitais a serem copiados.", False)]

    paragrafos = [
        primeira,
        [(f"Com o procedimento, aceito a imediata formatação {micro}, estando "
          f"ciente de que todos os dados eletrônicos {computador} serão apagados "
          "em definitivo.", False)],
        [("DECLARO AINDA", True),
         (" que todos os aplicativos, sistemas e sites utilizados nos computadores "
          "anteriores foram instalados e testados nos micros formatados/substituídos."
          if varias else
          " que todos os aplicativos, sistemas e sites utilizados no computador "
          "anterior foram instalados e testados no micro formatado/substituído.", False)],
    ]
    if trava:
        if varias:
            paragrafos.append(
                [("DECLARO", True), (", pelo presente, que a trava de segurança foi "
                 "instalada nas estações de trabalho ", False), ("INSTALADAS", True),
                 (" relacionadas neste documento e que recebi as chaves. Estou ciente "
                  "de que as chaves são necessárias para a abertura dos equipamentos "
                  "em caso de manutenção técnica.", False)])
        else:
            paragrafos.append(
                [("DECLARO", True), (", pelo presente, que a trava de segurança foi "
                 "instalada na estação de trabalho ", False), ("INSTALADA", True),
                 (" relacionada neste documento e que recebi a chave. Estou ciente de "
                  "que a chave é necessária para a abertura do equipamento em caso "
                  "de manutenção técnica.", False)])
    return paragrafos
