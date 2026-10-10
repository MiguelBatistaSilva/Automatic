"""Termos gerados pelo Assistente (10/10):
  - Termo de Responsabilidade de Instalação (troca de máquina) — odt.py;
  - Termo de Tarefa de Demanda (eventos) — demanda.py.
"""

import datetime
import pathlib
import re

from services.paths import APP_LOCAL_DIR
from services.termos import demanda
from services.termos.modelo import Equipamento, Pessoa, Termo, Troca
from services.termos.odt import gerar_odt, para_pdf

__all__ = ["Equipamento", "Pessoa", "Termo", "Troca", "gerar_odt", "para_pdf",
           "PASTA", "gerar", "gerar_demanda", "demanda"]

# Fora da pasta do projeto: arquivo novo lá dentro reinicia o backend do
# Reflex em desenvolvimento (hot-reload — ver services/paths.py).
PASTA = APP_LOCAL_DIR / "termos"


def _salvar(gerar_odt_de, termo, chamado: str, nome: str
            ) -> tuple[pathlib.Path, "pathlib.Path | None", str]:
    """Grava o .odt e o PDF em PASTA/<chamado>/. Devolve (odt, pdf, erro):
    sem LibreOffice o PDF falha, mas o .odt sai do mesmo jeito.

    Nome com hora: gerar de novo não esbarra num PDF aberto no visualizador
    (o Windows não deixa sobrescrever arquivo aberto)."""
    pasta = re.sub(r"[^\w-]", "", chamado or "") or "sem_chamado"
    agora = datetime.datetime.now()
    odt = gerar_odt_de(termo, PASTA / pasta / f"{nome} {agora:%Y-%m-%d %Hh%Mmin%S}.odt")
    try:
        return odt, para_pdf(odt), ""
    except Exception as e:
        return odt, None, str(e)


def gerar(termo: Termo):
    """Termo de Responsabilidade de Instalação (troca de máquina)."""
    chamado = re.sub(r"[^\w-]", "", termo.chamado or "") or "sem_chamado"
    tipo = "com backup" if termo.backup else "sem backup"
    return _salvar(gerar_odt, termo, termo.chamado, f"Termo {chamado} {tipo}")


def gerar_demanda(termo: "demanda.TermoDemanda"):
    """Termo de Tarefa de Demanda (eventos)."""
    chamado = re.sub(r"[^\w-]", "", termo.chamado or "") or "sem_chamado"
    return _salvar(demanda.gerar_odt, termo, termo.chamado, f"{chamado}_DEMANDA")
