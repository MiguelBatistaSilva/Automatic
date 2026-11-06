"""
eval_agente.py — Prova com gabarito do COMPORTAMENTO do Assistente (04/11).

O eval_roteador.py confere só a escolha do domínio. Este confere o que o
técnico recebe: o cartão certo, a pergunta certa. O gabarito vem do técnico:
chamado analisado junto vira um caso aqui.

Duas partes:
  - REGRAS: as ferramentas sem a IA (grátis, menos de 1 s). Rodar a cada mudança.
  - IA (--ia): a conversa com o modelo de verdade. Gasta a cota da chave e leva
    minutos; o modelo varia, por isso cada caso roda --rodadas vezes, com um
    número de chamado diferente em cada (a escolha da IA muda até com o número).

NÃO abre o Assyst nem o Itom: a sessão, a ficha e o Itom são falsos, e os chamados e tombos são
inventados. Só o texto destes casos vai para a plataforma de IA.

Uso:
    python scripts/eval_agente.py                 (só as regras)
    python scripts/eval_agente.py --ia            (regras + IA, Gemini, 3 rodadas)
    python scripts/eval_agente.py --ia --modelo groq --rodadas 1 --caso um_tombo

Sai com código 1 se algum caso falhar.
"""

import argparse
import dataclasses
import datetime
import os
import re
import sys
import time
from typing import Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.agente import assistente, cartao, ferramentas, ficha, llm, sessao
from services.agente.ferramentas import FERRAMENTAS, Acao, ChameDeNovo
from services.fluxos.flow_itom_pw import Maquina

DOIS_TOMBOS = "Solicito a desmontagem de dois computadores. Tombos 111111 e 222222."
SEM_TOMBO = "Solicito a desmontagem dos computadores do setor."
UM_TOMBO = "Computador não liga. Tombo 333333."
SEM_EQUIPAMENTO = "Usuário sem acesso ao PJe."

TROCA = "Troca de computador."
VELHA = Maquina("666666", hostname="FCB13TESTE666666", serial="SERIE666",
                marca_modelo="POSITIVO C6200")
NOVA = Maquina("777777", hostname="FCB13TESTE777777", serial="SERIE777",
               marca_modelo="LENOVO 13E0S00400")

AMANHA = datetime.date.today() + datetime.timedelta(days=1)
ONTEM = datetime.date.today() - datetime.timedelta(days=1)

_descricoes: dict[str, str] = {}   # número do chamado -> descrição da ficha falsa
_no_itom: "list[Maquina] | None" = [VELHA, NOVA]   # None = Itom fora do ar


class SessaoFalsa:
    log = staticmethod(lambda *a, **k: None)

    def __init__(self, *a, **k):
        pass

    def pagina(self):
        return object()

    def fechar(self):
        pass


def _ficha_falsa(pagina, numero, log, recente=True):
    descricao = _descricoes.get(numero.strip().upper())
    if descricao is None:
        return None
    return ficha.Ficha(numero=numero, secao="SETOR FICTICIO", edificio="Edificio Ficticio",
                       item_b="", categoria="Instalar / Configurar", descricao=descricao)


def _itom_falso(tombos, s):
    if _no_itom is None:
        return {}
    achadas = {m.tombo: m for m in _no_itom}
    return {t: achadas.get(t) for t in tombos}


# --------------------------------------------------------------------------- #
# REGRAS: a ferramenta, sem a IA
# --------------------------------------------------------------------------- #

def _preparar(texto_da_ficha: "str | None", /, **args) -> "Acao | str":
    """O caminho do assistente.py para uma ferramenta com leitura: antes + preparar.
    `texto_da_ficha` None = o chamado não abriu."""
    _descricoes.clear()
    if texto_da_ficha is not None:
        _descricoes["R1"] = texto_da_ficha
    f = FERRAMENTAS["desmembrar"]
    return f.preparar(f.antes({"chamado_pai": "R1", **args}, SessaoFalsa()))


def _termo(no_itom, /, saiu=None, entrou=None, **args) -> "Acao | str":
    """O termo só com os tombos, com estas máquinas no Itom."""
    global _no_itom
    _no_itom = no_itom
    _descricoes.clear()
    _descricoes["R1"] = TROCA
    f = FERRAMENTAS["gerar_termo"]
    r = f.preparar(f.antes({"chamado": "R1", "backup": False, "maquinas": [{
        "saiu": {"tombo": "666666", **(saiu or {})},
        "entrou": {"tombo": "777777", **(entrou or {})}}], **args}, SessaoFalsa()))
    _no_itom = [VELHA, NOVA]
    return r


def _maquinas_do_termo(r, saiu: tuple, entrou: tuple, no_aviso: str = "") -> str:
    """saiu/entrou = (série, hostname) esperados."""
    if isinstance(r, str):
        return f"não montou o cartão: {r}"
    t = r.args["maquinas"][0]
    viu = tuple((t[lado]["serie"], t[lado]["hostname"]) for lado in ("saiu", "entrou"))
    if viu != (saiu, entrou):
        return f"máquinas {viu}"
    if no_aviso and no_aviso not in r.aviso:
        return f"o aviso não traz '{no_aviso}': {r.aviso!r}"
    return "" if "?" not in "".join(r.linhas) else f"'?' no cartão: {r.linhas}"


def _programar(dia: str, espera: str) -> str:
    r = FERRAMENTAS["programar_atendimento"].preparar(
        {"chamados": ["R1234567"], "dia": dia, "hora": "10:00", "motivo": "teste"})
    texto = r if isinstance(r, str) else " ".join(r.linhas)
    return "" if espera in texto.lower() else f"esperava '{espera}': {texto!r}"


def _regras() -> list[tuple[str, str]]:
    """(nome, problema); problema vazio = passou."""
    def pede(r, *trechos):
        if not isinstance(r, str):
            return f"montou o cartão: {r.args}"
        faltam = [t for t in trechos if t not in r]
        return f"a mensagem não traz {faltam}: {r}" if faltam else ""

    def cartao_com(r, tombos, no_aviso=""):
        if isinstance(r, str):
            return f"não montou o cartão: {r}"
        if r.args["tombos"] != tombos:
            return f"tombos {r.args['tombos']}"
        if no_aviso and no_aviso not in r.aviso:
            return f"o aviso não traz '{no_aviso}': {r.aviso!r}"
        if not no_aviso and r.aviso:
            return f"aviso inesperado: {r.aviso!r}"
        return ""

    def forca(r, *trechos):
        return pede(r, *trechos) or ("" if isinstance(r, ChameDeNovo) else "não forçou a nova chamada")

    # Como chega a 2ª chamada, depois do ChameDeNovo, com o técnico de acordo.
    d = {"descricao": "Desmontagem de computador.", "conferido": True, "_refeita": True}
    return [
        ("só o número: devolve o Pedido e força a nova chamada",
         forca(_preparar(DOIS_TOMBOS), "desmontagem")),
        ("descrição sem ter visto o Pedido: devolve o Pedido",
         forca(_preparar(DOIS_TOMBOS, descricao="Instalação de computador.", conferido=True),
               "desmontagem")),
        ("descrição conferida: cartão com os tombos do chamado",
         cartao_com(_preparar(DOIS_TOMBOS, **d), ["111111", "222222"])),
        ("sem tombos, com equipamento: pede os tombos",
         pede(_preparar(SEM_TOMBO), "tombos")),
        ("sem equipamento: avisa que não parece caso de desmembrar",
         pede(_preparar(SEM_EQUIPAMENTO), "não cita equipamento", "PJe")),
        ("sem equipamento, técnico insiste com tombos: cartão com aviso",
         cartao_com(_preparar(SEM_EQUIPAMENTO, tombos=["444444", "555555"], **d),
                    ["444444", "555555"], "não cita equipamento")),
        ("1 tombo: questiona",
         pede(_preparar(UM_TOMBO, descricao="Manutenção."), "1 tombo")),
        ("1 tombo confirmado: cartão com 1 filho",
         cartao_com(_preparar(UM_TOMBO, **d), ["333333"])),
        ("tombos diferentes do chamado: usa os do técnico, com aviso",
         cartao_com(_preparar(DOIS_TOMBOS, tombos=["444444", "555555"], **d),
                    ["444444", "555555"], "111111")),
        ("tombos iguais aos do chamado: sem aviso",
         cartao_com(_preparar(DOIS_TOMBOS, tombos=["222222", "111111"], **d),
                    ["222222", "111111"])),
        ("chamado não abriu: segue com o que o técnico disse",
         cartao_com(_preparar(None, tombos=["444444", "555555"],
                              descricao="Desmontagem de computador."),
                    ["444444", "555555"])),
        # Gabarito do técnico (05/11): só os tombos; hostname do Itom; fora do Itom,
        # a nova herda o nome da antiga, e sem nada sai só o tombo.
        ("termo: marca/modelo vem do Itom, a dita pelo técnico vale mais",
         "" if [(lambda t: (t["saiu"]["marca_modelo"], t["entrou"]["marca_modelo"]))(
             _termo([VELHA, NOVA], entrou={"marca_modelo": "DELL 7010"}).args["maquinas"][0])]
         == [("POSITIVO C6200", "DELL 7010")] else "marca/modelo errada"),
        ("termo: as duas no Itom, cada uma com o seu nome",
         _maquinas_do_termo(_termo([VELHA, NOVA]), ("SERIE666", VELHA.hostname),
                            ("SERIE777", NOVA.hostname))),
        ("termo: a nova fora do Itom herda o nome da antiga",
         _maquinas_do_termo(_termo([VELHA]), ("SERIE666", VELHA.hostname),
                            ("", VELHA.hostname), "777777 não está")),
        ("termo: a antiga fora do Itom não pega o nome da nova",
         _maquinas_do_termo(_termo([NOVA]), ("", ""), ("SERIE777", NOVA.hostname))),
        ("termo: nenhuma no Itom sai só com os tombos",
         _maquinas_do_termo(_termo([]), ("", ""), ("", ""), "666666 não está")),
        ("termo: Itom fora do ar avisa no cartão",
         _maquinas_do_termo(_termo(None), ("", ""), ("", ""), "Não consegui consultar o Itom")),
        ("termo: nome ditado vale para os dois, a série vem do Itom",
         _maquinas_do_termo(_termo([VELHA, NOVA], saiu={"hostname": "FCB13DITADO"}),
                            ("SERIE666", "FCB13DITADO"), ("SERIE777", "FCB13DITADO"))),
        ("termo: nome solto no pedido vale para os dois",
         _maquinas_do_termo(_termo([VELHA, NOVA], nome="FCB13SOLTO"),
                            ("SERIE666", "FCB13SOLTO"), ("SERIE777", "FCB13SOLTO"))),
        ("programar: o cartão avisa do início automático",
         _programar(AMANHA.strftime("%d/%m"), "início automático")),
        ("programar: hora que já passou volta como pergunta",
         _programar(ONTEM.strftime("%d/%m"), "já passou")),
    ]


# --------------------------------------------------------------------------- #
# IA: a conversa de verdade
# --------------------------------------------------------------------------- #

def _sem_cartao(r: assistente.Resposta) -> str:
    if r.acoes:
        return f"montou o cartão: {r.acoes[0].args.get('tombos')}"
    # Pergunta no meio também vale ("Qual chamado? Me passa o número.").
    pediu = re.search(r"\?|\bme (passa|diz|fala|d[áa]|manda)\b", r.texto, re.I)
    return "" if pediu else f"não perguntou: {r.texto!r}"


def _cartao(r: assistente.Resposta, tombos: list[str], no_aviso: str = "",
            descricao_tem: str = "") -> str:
    if len(r.acoes) != 1 or r.acoes[0].ferramenta != "desmembrar":
        return f"sem o cartão de desmembrar: {r.texto!r}"
    a = r.acoes[0]
    if a.args["tombos"] != tombos:
        return f"tombos {a.args['tombos']}"
    if no_aviso and no_aviso not in a.aviso:
        return f"o aviso não traz '{no_aviso}': {a.aviso!r}"
    if descricao_tem and descricao_tem not in a.args["descricao"].lower():
        return f"descrição dos filhos errada: {a.args['descricao']!r}"
    return ""


def _cartao_termo(r: assistente.Resposta) -> str:
    if len(r.acoes) != 1 or r.acoes[0].ferramenta != "gerar_termo":
        return f"sem o cartão do termo: {r.texto!r}"
    return _maquinas_do_termo(r.acoes[0], ("SERIE666", VELHA.hostname), ("SERIE777", NOVA.hostname))


def _pede_sem_ficha_tecnica(padrao: str) -> Callable[[assistente.Resposta], str]:
    """Pergunta sobre `padrao`, sem pedir o que vem do Itom."""
    cita = _sem_cartao_e_cita(padrao)
    def conferir(r):
        pediu = re.search(r"marca|modelo|s[ée]rie|hostname", r.texto, re.I)
        return cita(r) or (f"pediu dado do Itom: {r.texto!r}" if pediu else "")
    return conferir


def _sem_cartao_e_cita(padrao: str) -> Callable[[assistente.Resposta], str]:
    def conferir(r):
        problema = _sem_cartao(r)
        if problema:
            return problema
        return "" if re.search(padrao, r.texto, re.I) else f"não falou de '{padrao}': {r.texto!r}"
    return conferir


def _ferramenta(nome: str) -> Callable[[assistente.Resposta], str]:
    def conferir(r):
        feitas = [a.ferramenta for a in r.acoes]
        return "" if feitas == [nome] else f"esperava {nome}, veio {feitas}: {r.texto!r}"
    return conferir


@dataclasses.dataclass
class Caso:
    nome: str
    descricao: str
    turnos: list[str]     # o que o técnico diz; {n} = o número do chamado
    conferir: Callable[[assistente.Resposta], str]   # olha a resposta do último turno


CASOS = [
    Caso("dois_tombos", DOIS_TOMBOS, ["desmembra o {n}"],
         lambda r: _cartao(r, ["111111", "222222"], descricao_tem="desmont")),
    Caso("sem_tombo", SEM_TOMBO, ["desmembra o {n}"], _sem_cartao_e_cita("tombo")),
    # Gabarito do técnico (03/11): 1 tombo -> questionar, e obedecer se confirmar.
    Caso("um_tombo", UM_TOMBO, ["desmembra o {n}"],
         _sem_cartao_e_cita(r"\b(1|um|único)\b.{0,12}tombo|tombo (só|único)")),
    Caso("um_tombo_confirmado", UM_TOMBO, ["desmembra o {n}", "sim, pode desmembrar assim mesmo"],
         lambda r: _cartao(r, ["333333"])),
    # Gabarito (03/11): sem equipamento -> avisar, e obedecer se insistir.
    Caso("sem_equipamento", SEM_EQUIPAMENTO, ["desmembra o {n}"],
         _sem_cartao_e_cita("equipamento")),
    Caso("sem_equipamento_insiste", SEM_EQUIPAMENTO,
         ["desmembra o {n}", "desmembra sim, tombos 444444 e 555555"],
         lambda r: _cartao(r, ["444444", "555555"], no_aviso="não cita equipamento")),
    # Gabarito (03/11): tombos diferentes -> usa os do técnico, com aviso no cartão.
    Caso("tombos_diferentes", DOIS_TOMBOS, ["desmembra o {n} nos tombos 444444 e 555555"],
         lambda r: _cartao(r, ["444444", "555555"], no_aviso="111111")),
    # A análise some no turno seguinte: a descrição dos filhos não pode ser inventada.
    Caso("depois_da_analise", DOIS_TOMBOS, ["analisa o {n}", "então desmembra"],
         lambda r: _cartao(r, ["111111", "222222"], descricao_tem="desmont")),
    Caso("sem_numero", DOIS_TOMBOS, ["desmembra esse chamado aí"], _sem_cartao),
    # Gabarito (05/11): o técnico passa só os tombos; o resto vem do Itom.
    Caso("termo_so_tombos", TROCA, ["termo sem backup do {n}: 666666 -> 777777"], _cartao_termo),
    Caso("termo_sem_backup_dito", TROCA, ["termo do {n}: 666666 -> 777777"],
         _pede_sem_ficha_tecnica("backup")),
    Caso("termo_sem_tombos", TROCA, ["termo sem backup do {n}"],
         _pede_sem_ficha_tecnica("tombo")),
    # Início agendado (05/11).
    Caso("programar", TROCA,
         [f"programa o {{n}} para {AMANHA:%d/%m} às 14:00, motivo: usuário em audiência"],
         _ferramenta("programar_atendimento")),
    Caso("programar_sem_hora", TROCA, ["programa o {n}, motivo: usuário em audiência"],
         _sem_cartao),
    Caso("iniciar_agora", TROCA, ["inicia o atendimento do {n} agora"],
         _ferramenta("iniciar_atendimento")),
    Caso("ver_agendados", TROCA, ["quais chamados estão agendados para iniciar?"],
         _ferramenta("consultar_agendados")),
    Caso("cancelar_agendado", TROCA, ["cancela o início agendado do {n}"],
         _ferramenta("cancelar_agendado")),
]


def _responder(historico: list[dict], modelo: str) -> assistente.Resposta:
    """Espera e tenta de novo no limite por minuto do plano grátis."""
    for tentativa in range(3):
        try:
            return assistente.responder(historico, "teste", "teste", modelo_id=modelo)
        except llm.ErroLLM as e:
            if tentativa == 2 or "por minuto" not in str(e):
                raise
            time.sleep(60)


def _conversa(caso: Caso, numero: str, modelo: str, pausa: float) -> assistente.Resposta:
    historico: list[dict] = []
    r = None
    for turno in caso.turnos:
        time.sleep(pausa)
        historico.append({"role": "user", "content": turno.format(n=numero)})
        r = _responder(historico, modelo)
        # O mesmo que o state/assistente_state.py guarda: só texto e notas.
        ja = cartao.nota_lembrar(r.lembrar)
        conteudo = cartao.nota_plano(r.acoes, True) if r.acoes else r.texto
        historico.append({"role": "assistant", "content": conteudo + ja})
    return r


def _ia(modelo: str, rodadas: int, pausa: float, so_caso: str) -> int:
    casos = [c for c in CASOS if not so_caso or c.nome == so_caso]
    certos = total = tokens = 0
    for i, caso in enumerate(casos):
        acertos = 0
        for rodada in range(rodadas):
            numero = f"R99{i:02d}{rodada:03d}"
            _descricoes.clear()
            _descricoes[numero] = caso.descricao
            total += 1
            try:
                r = _conversa(caso, numero, modelo, pausa)
                problema = caso.conferir(r)
                tokens += r.metricas.get("tokens_entrada", 0)
            except llm.ErroLLM as e:
                problema = f"erro da IA: {e}"
            if problema:
                print(f"   ❌ {caso.nome} ({numero}): {' '.join(problema.split())[:220]}")
            else:
                acertos += 1
        certos += acertos
        print(f"{'✅' if acertos == rodadas else '❌'} {caso.nome}: {acertos} de {rodadas}")
    print(f"\nIA ({modelo}): {certos} de {total} certos · "
          f"~{tokens // max(total, 1)} tokens de entrada no último turno de cada conversa")
    return total - certos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--ia", action="store_true", help="roda também com o modelo de verdade")
    ap.add_argument("--so-ia", action="store_true", help="pula as regras")
    ap.add_argument("--modelo", default="gemini", choices=list(llm.MODELOS))
    ap.add_argument("--rodadas", type=int, default=3)
    ap.add_argument("--caso", default="", help="roda só este caso da IA")
    ap.add_argument("--pausa", type=float, default=10, help="segundos antes de cada ida (limite grátis)")
    a = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    # A troca que mantém o Assyst de fora: nada aqui abre navegador.
    sessao.Sessao = SessaoFalsa
    ficha.ler_ficha = _ficha_falsa
    ferramentas._itom = _itom_falso

    falhas = 0
    if not a.so_ia:
        regras = _regras()
        for nome, problema in regras:
            if problema:
                falhas += 1
                print(f"❌ {nome}\n     {problema}")
        print(f"Regras: {len(regras) - falhas} de {len(regras)} certas\n")
    if a.ia or a.so_ia:
        falhas += _ia(a.modelo, a.rodadas, a.pausa, a.caso)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
