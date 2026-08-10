"""
services/assyst_common.py — Helpers do Assyst que NAO dependem de navegador.

Sao Python/pandas/arquivo puro: URLs, normalizacao de id, montagem da descricao
a partir da linha do CSV e o registro/abertura do TXT de chamados filhos. Antes
viviam no `flow_utils.py` (Selenium) e eram reaproveitados pelo codigo Playwright;
com a migracao completa, foram movidos para ca para que nenhum modulo vivo precise
importar o `flow_utils` (e, com ele, o proprio Selenium).
"""

import os
from pathlib import Path

import pandas as pd

from services.paths import DATA_DIR

_URL_HOME = "https://cati.tjce.jus.br/assystweb/application.do"
_URL_CHAMADO = (
    "https://cati.tjce.jus.br/assystweb/application.do"
    "#event%2FDisplayEvent.do%3Fdispatch%3DgetEvent"
    "%26checkJukeBoxSettings%3Dtrue%26eventId%3D{id_final}%26resultSet%3D"
)

# Tela de abertura de Requisicao de Servico (chamado do zero, sem chamado-pai).
# O `entRef=ES3` no fim NAO e enfeite: e o identificador do tipo de requisicao, e e
# dele que saem os ids do formulario (`ManageEventForm_ES3_...`, `rtES3_formattedRemarks`).
# Trocar o entRef muda a tela E os ids — por isso o fluxo descobre o prefixo lendo a
# propria pagina (ver services/requisicao_campos.descobrir_prefixo) em vez de fixar "ES3".
_URL_REQUISICAO = (
    "https://cati.tjce.jus.br/assystweb/application.do"
    "#event%2FLogChangeHandler.do%3Fdispatch%3DprepareChange"
    "%26ncAction%3DCLEARHISTORY%26entRef%3DES3"
)
_FILHOS_DIR = DATA_DIR


def _path_filhos(numero_chamado: str) -> Path:
    _FILHOS_DIR.mkdir(parents=True, exist_ok=True)
    nome = numero_chamado.strip().replace("/", "_").replace("\\", "_")
    return _FILHOS_DIR / f"filhos_{nome}.txt"


def _registrar_filho(numero_chamado: str, numero_filho_str: str) -> None:
    """Adiciona o numero do filho ao TXT, sem duplicatas."""
    if not numero_filho_str:
        return
    p = _path_filhos(numero_chamado)
    existentes = set()
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            existentes = {linha.strip() for linha in f if linha.strip()}
    if numero_filho_str.strip() not in existentes:
        with open(p, "a", encoding="utf-8") as f:
            f.write(numero_filho_str.strip() + "\n")


def _abrir_txt_filhos(numero_chamado: str) -> None:
    """Abre o TXT de filhos no Bloco de Notas se existir e tiver conteudo."""
    p = _path_filhos(numero_chamado)
    if p.exists() and p.stat().st_size > 0:
        os.startfile(str(p))


def _normalizar_id_assyst(numero: str) -> str:
    n = str(numero).strip().upper()
    if n.startswith("S2"):
        return "7" + n[2:]
    if n.startswith("R2"):
        return "7" + n[2:]
    if n.isdigit():
        return f"1{n}"
    return n


def _so_o_nome(bruto: str) -> str:
    """Extrai o nome de um valor de lookup renderizado pelo Assyst.

    O type-ahead grava no campo a forma `matricula(NOME)` — confirmado em tela
    viva tanto na criacao (`905245(RIBAMAR...)`) quanto num chamado ja salvo
    (`905513(JHONATAN NASCIMENTO DA COSTA)`). Aqui interessa so o miolo.

    NUNCA devolve vazio se recebeu algo: sem parentese, ou com parentese
    malformado, devolve o valor bruto. Uma linha de resultado com a matricula
    ainda identifica o chamado; uma vazia, nao.

    Mora aqui, e nao num fluxo, porque a Requisição (le da tela de criacao) e a
    Analise de SLA (le da tela do chamado salvo) precisam da MESMA regra.
    """
    bruto = (bruto or "").strip()
    if not bruto:
        return ""
    ini = bruto.find("(")
    if ini == -1:
        return bruto
    fim = bruto.rfind(")")
    return bruto[ini + 1:fim if fim > ini else None].strip() or bruto


def _montar_descricao(template: str, row) -> str:
    resultado = template
    for col, valor in row.items():
        marcador = "{{" + str(col) + "}}"
        valor_str = "" if pd.isna(valor) else str(valor).strip()
        resultado = resultado.replace(marcador, valor_str)
    return resultado
