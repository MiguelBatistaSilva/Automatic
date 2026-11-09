"""
services/agente/ferramentas/base.py — As peças que toda ferramenta usa.

`Acao` (o cartão), `Ferramenta` (o registro no catálogo), `ChameDeNovo` e os
ajudantes comuns: listas de números, tombo, nomes sem acento e a conferência
no banco de referência. Sem dependência dos outros módulos do pacote.
"""

import dataclasses
import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from services.agente.sessao import Sessao

# Esquemas repetidos no catálogo. ENXUTO DE PROPÓSITO (06/10): vão em toda
# ida ao modelo; regra de negócio mora em conhecimento/*.md.
_CHAMADOS = {"type": "array", "items": {"type": "string"}}
# A fila é conferida no código (erro devolve as válidas) — sem `enum` aqui.
_FILA = {"type": "string", "description": "Fila do SLA."}


@dataclasses.dataclass
class Acao:
    ferramenta: str
    args: dict
    titulo: str
    linhas: list[str]
    escreve: bool
    pode_simular: bool = False
    # Situação do checkpoint (fluxos com retomada): "", "novo", "pendente",
    # "concluido" ou "corrompido" — decide quais botões o cartão mostra.
    checkpoint: str = ""
    aviso: str = ""
    # Texto do botão "Copiar lista" do cartão. Na Requisição é o lote EXATO:
    # colado de volta no chat, vira o mesmo lote (ver requisicoes_coladas).
    copiar: str = ""
    # False = roda só no computador do técnico (ex.: gerar o termo): sem
    # login nem navegador, se o plano inteiro for assim (10/10).
    assyst: bool = True


class ChameDeNovo(str):
    """O `preparar` precisa que a IA complete o pedido com o que a mensagem traz,
    sem o técnico. O assistente.py FORÇA a nova chamada: só pedindo em texto, a
    IA às vezes respondia "vou mandar ver" e o cartão não saía (04/11). Na nova
    chamada os args chegam com `_refeita`=True."""


@dataclasses.dataclass
class Ferramenta:
    nome: str
    # Texto fixo, ou função que monta na hora (ex.: lê tipos/nomes do banco).
    descricao: "str | Callable[[], str]"
    parametros: dict
    preparar: Callable[[dict], "Acao | str"]
    executar: Callable[[dict, "Sessao"], "Resultado"] | None = None
    # Ferramenta LOCAL (sem navegador): roda na hora e o resultado volta ao
    # modelo — só para dados do próprio app, nunca do Assyst.
    local: Callable[[dict], str] | None = None
    # Ferramenta de INVESTIGAÇÃO (2026-10-01): lê o Assyst DURANTE a conversa
    # e o resultado volta ao modelo, para ele decidir o próximo passo (ex.:
    # SLA estourado -> não resolver). Só leitura, e o texto devolvido leva o
    # MÍNIMO (número do chamado, tempo do SLA; nome só de quem o técnico citou).
    investiga: Callable[[dict, "Sessao"], str] | None = None
    # DOMÍNIO (07/10): só vai para a IA quando o pedido é desse domínio (ver
    # services/agente/roteador.py). Mesmo nome da subpasta em conhecimento/.
    # "geral" = vai sempre. Tupla = vale em mais de um (ex.: achar o chamado
    # pelo nome serve a chamados E a termos).
    dominio: "str | tuple[str, ...]" = "geral"
    # LEITURA PELO CÓDIGO antes do `preparar` (10/10): busca no Assyst o que
    # o cartão precisa e a IA não deve ver (ex.: matrícula do usuário
    # afetado, LGPD) — sem ida a mais à IA. Recebe os args e a Sessao e
    # devolve os args completados; quem chama trata falha como "não leu".
    antes: Callable[[dict, "Sessao"], dict] | None = None
    # QUANDO rodar o `antes` (21/10). Sem isto: só com o pedido completo. Com
    # isto: quando ela disser — a leitura pode ser justamente o que responde
    # a pergunta (ex.: em que fila o chamado está, na Atribuição Interna).
    precisa_ler: Callable[[dict], bool] | None = None


# --------------------------------------------------------------------------- #
# Ajudantes
# --------------------------------------------------------------------------- #

def _lista(v) -> list[str]:
    """Normaliza uma lista de números (chamados/tombos): aceita lista ou texto
    separado por vírgula/espaço, tira vazios e repetidos, mantém a ordem."""
    if isinstance(v, str):
        v = v.replace(",", " ").replace(";", " ").split()
    vistos, saida = set(), []
    for x in v or []:
        x = str(x).strip()
        if x and x not in vistos:
            vistos.add(x)
            saida.append(x)
    return saida


def _lista_curta(itens: list[str], limite: int = 12) -> str:
    if len(itens) <= limite:
        return ", ".join(itens)
    return ", ".join(itens[:limite]) + f" … (+{len(itens) - limite})"


def _ok_falha(ok: bool) -> str:
    return "✅" if ok else "❌"


def normalizar_tombo(t: str) -> str:
    """'FCBVCUSTO265287' -> '265287'; '*333284' -> '333284'. Regra do usuário:
    o tombo são os 6 últimos dígitos do código da máquina."""
    numeros = re.findall(r"\d+", str(t))
    if not numeros:
        raise ValueError(f"Tombo sem número: '{t}'.")
    ultimo = numeros[-1]
    return ultimo[-6:] if len(ultimo) >= 6 else ultimo


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def _resolver_nome(valor: str, opcoes: list[str], rotulo: str) -> tuple[str, str]:
    """(nome_cadastrado, erro). Aceita parte do nome ('Arthur' -> o nome
    completo) se só UM cadastrado bater; ambíguo ou desconhecido vira
    pergunta, nunca chute."""
    alvo = _sem_acento(valor or "").strip()
    if not alvo:
        return "", f"Falta {rotulo}. Pergunte ao técnico."
    for o in opcoes:
        if _sem_acento(o) == alvo:
            return o, ""
    palavras = alvo.split()
    batem = [o for o in opcoes if all(p in _sem_acento(o) for p in palavras)]
    if len(batem) == 1:
        return batem[0], ""
    if len(batem) > 1:
        return "", (f"{rotulo} '{valor}' é ambíguo: {', '.join(batem)}. "
                    "Pergunte qual.")
    lista = f"Cadastrados: {', '.join(opcoes)}. " if len(opcoes) <= 15 else ""
    return "", (f"{rotulo} '{valor}' não está cadastrado. {lista}"
                f"Pergunte ao técnico qual é (ou peça para "
                "cadastrar em Configurações -> Referência).")


def _conferir(campo: str, dito: str, avisos: list[str],
              confirmados: "list | None" = None, brando: bool = False) -> tuple[str, str]:
    """(valor, erro) de um campo com tabela no banco de referência (28/10:
    o técnico pode errar ao escrever — tudo passa por aqui).

    Corrigido -> usa o do banco e anota a troca em `avisos` (vai ao cartão).
    Ambíguo -> pergunta. Não achou -> pergunta com os mais próximos; se o
    técnico confirmou (campo em `confirmados`), segue com aviso;
    `confirmados=None` = o campo não aceita valor de fora. `brando`
    (edifício: a lista ainda é incompleta) segue com aviso sem perguntar."""
    from services.dados import referencia

    rotulo = referencia.ROTULOS.get(campo, campo)
    c = referencia.conferir(campo, dito)
    if c.ok:
        if c.corrigido:
            avisos.append(f"{rotulo}: '{c.dito}' → '{c.valor}'.")
        return c.valor, ""
    if c.opcoes:
        return "", f"{rotulo} '{c.dito}' é ambíguo: {', '.join(c.opcoes)}. Pergunte qual."
    if brando or campo in (confirmados or []):
        avisos.append(f"{rotulo} '{c.dito}' não está na referência.")
        return c.dito, ""
    perto = f" Mais próximos: {', '.join(c.proximos)}." if c.proximos else ""
    erro = f"{rotulo} '{c.dito}' não está na referência.{perto} Pergunte ao técnico qual é"
    if confirmados is None:
        return "", erro + "."
    return "", (erro + f"; se ele confirmar que '{c.dito}' está certo, chame de "
                f"novo com confirmados=['{campo}'].")


# Itom: usado pelo termo, pelo despacho e pela investigação. Quem chama usa
# base._itom(...) — assim o eval_agente.py troca por um falso num ponto só.
def _itom(tombos: list[str], s: Sessao) -> dict:
    """{tombo: Maquina|None} pelo Itom (30/10); {} se não deu para entrar.
    Em outra thread (06/11): o Assyst pode já estar aberto nesta, e o Playwright
    sync não abre um segundo navegador na mesma thread. Esta fica esperando."""
    from services.fluxos.flow_itom_pw import consultar
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(consultar, tombos, s.matricula, s.senha, s.log).result()
    except Exception as e:
        # O log da conversa não aparece em lugar nenhum: vai também para o terminal.
        logging.getLogger("agente").error("Itom: %s", e)
        s.log(f"Não consegui consultar o Itom: {e}", "error")
        return {}
