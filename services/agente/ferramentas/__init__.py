"""
services/agente/ferramentas/ — O que o Assistente sabe fazer.

Pacote desde 09/11 (era um arquivo só, de 2.870 linhas). Cada arquivo traz
as funções E as entradas `Ferramenta(...)` do seu assunto:

  base.py          Acao, Ferramenta, ChameDeNovo e os ajudantes comuns (+ _itom)
  verificacoes.py  o que se confere antes de gravar: Edifício/Item B, relógio
  investigacao.py  só leitura: achar chamado, SLA, triagem, máquina
  bases.py         Bases de Conhecimento, desmembrar, aplicar base
  requisicao.py    Requisição de Serviço, por tombo, plantões
  acoes.py         resolver, corrigir, ações em lote, atribuir, programar, filas
  despacho.py      despacho ao Serviço de Operações
  termos.py        termo de responsabilidade e termo de demanda
  __init__.py      junta o catálogo (FERRAMENTAS), esquemas para a IA, executar

Ferramenta nova: entra na lista FERRAMENTAS do arquivo do assunto e, se a
posição importar, em _ORDEM aqui. Os nomes reexportados abaixo são os que
código de fora (assistente, bot, tela, evals, testes) importa daqui.

Cada ferramenta tem quatro partes:
  1. o ESQUEMA que o modelo enxerga (nome, descrição, parâmetros);
  2. `preparar(args)` — valida e normaliza o que o modelo mandou e monta o
     cartão (`Acao`). Devolve `str` quando falta algo: a mensagem volta ao
     modelo, que pergunta ao técnico em vez de chutar;
  3. `executar(args, sessao)` — roda de verdade, chamando os fluxos
     (services/fluxos/flow_*_pw.py) na página da `Sessao` do plano: um login e uma
     licença para todos os passos (2026-10-01; antes cada ferramenta abria o
     próprio Chrome via bot/services/*). NENHUM arquivo de fluxo foi alterado;
  4. o texto do RESULTADO, montado aqui (determinístico), e não pelo modelo.

LGPD: o resultado da execução (nomes, setores lidos do Assyst) NÃO volta para
a IA — vai direto para a tela. A IA só vê o que o técnico digitou e uma nota
curta de que a ação rodou.

`escreve=True` -> cartão com Confirmar/Cancelar antes de rodar.
`escreve=False` -> só leitura, roda direto (princípio combinado: ler sozinho,
gravar só com confirmação).
"""

from services.agente.sessao import ErroSessao, Resultado, Sessao
from services.agente.ferramentas import (
    acoes, base, bases, despacho, investigacao, requisicao, termos,
)
from services.agente.ferramentas.base import Acao, ChameDeNovo, Ferramenta

# Reexportados para quem importa daqui (assistente.py, agendados.py, evals, testes).
from services.agente.ferramentas.base import _lista, _lista_curta  # noqa: F401
from services.agente.ferramentas.verificacoes import _pausa_atual  # noqa: F401
from services.agente.ferramentas.requisicao import requisicoes_coladas  # noqa: F401
from services.agente.ferramentas.acoes import _exec_programar, _prep_programar  # noqa: F401
from services.agente.ferramentas.despacho import _prep_despacho  # noqa: F401
from services.agente.ferramentas.termos import _maquinas_do_itom  # noqa: F401


# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #

# ENXUTO DE PROPÓSITO (06/10): os esquemas vão em TODA ida ao modelo
# (~5.200 tokens por ida antes do enxugamento, 70% deles no catálogo). Regra
# de negócio NÃO entra neles: mora em conhecimento/*.md (fonte única). Só o
# que a ferramenta faz e o formato dos campos.

# A ordem em que as ferramentas vão para a IA: a mesma de antes da divisão
# em arquivos (09/11). Ferramenta nova fora desta lista vai para o fim.
_ORDEM = (
    "consultar_conhecimento",
    "buscar_chamado_por_usuario",
    "resolver_chamado",
    "verificar_sla",
    "analisar_chamado",
    "consultar_maquina",
    "corrigir_chamado",
    "listar_bases_conhecimento",
    "desmembrar",
    "aplicar_base",
    "criar_requisicoes",
    "criar_requisicoes_por_tombo",
    "criar_plantoes",
    "iniciar_atendimento",
    "programar_atendimento",
    "consultar_agendados",
    "cancelar_agendado",
    "adicionar_informacao",
    "aguardar_fornecedor",
    "atribuir_chamado",
    "despachar_operacao",
    "aguardar_usuario",
    "info_recebida_usuario",
    "info_recebida_fornecedor",
    "configurar_filas",
    "analisar_sla",
    "gerar_termo",
    "gerar_termo_demanda",
)


def _montar(*listas: list[Ferramenta]) -> dict[str, Ferramenta]:
    todas = [f for lista in listas for f in lista]
    pos = {n: i for i, n in enumerate(_ORDEM)}
    todas.sort(key=lambda f: pos.get(f.nome, len(_ORDEM)))
    return {f.nome: f for f in todas}


FERRAMENTAS: dict[str, Ferramenta] = _montar(
    investigacao.FERRAMENTAS, bases.FERRAMENTAS, requisicao.FERRAMENTAS,
    acoes.FERRAMENTAS, despacho.FERRAMENTAS, termos.FERRAMENTAS,
)


def _aceita_null(parametros: dict) -> dict:
    """Campos OPCIONAIS aceitam null. A Groq valida a chamada contra o esquema
    e recusava (erro 400) quando o modelo mandava null num opcional — ex.:
    `setor: null` no buscar_chamado_por_usuario (visto em 01/10)."""
    obrigatorios = set(parametros.get("required", []))
    props = {}
    for nome, p in parametros.get("properties", {}).items():
        if nome not in obrigatorios and isinstance(p.get("type"), str):
            p = {**p, "type": [p["type"], "null"]}
        props[nome] = p
    return {**parametros, "properties": props}


_ULTIMA_ACAO = {
    "type": "boolean",
    # Explicado UMA vez no SISTEMA (vai em ~14 ferramentas; era 180 chars cada).
    "description": "Última ação do pedido?",
}


def _com_ultima_acao(f: Ferramenta, parametros: dict) -> dict:
    """Ferramentas de AÇÃO ganham o campo obrigatório `ultima_acao` (02/10).

    Com ele o modelo diz, já ao pedir o passo, se é o último — e o
    assistente.py não precisa de mais uma ida à IA só para ouvir "acabou" e
    a frase final. Essa ida extra, medida em 02/10, levava ~24 s de um pedido
    de 37 s (estourava o limite de tokens/minuto da Groq)."""
    if f.local or f.investiga or not f.executar:
        return parametros
    return {**parametros,
            "properties": {**parametros.get("properties", {}), "ultima_acao": _ULTIMA_ACAO},
            "required": list(parametros.get("required", [])) + ["ultima_acao"]}


def esquemas(dominios: "set[str] | None" = None) -> list[dict]:
    """As ferramentas para a IA: as dos `dominios` + as "geral".
    None = todas (o roteador não reconheceu o pedido)."""
    return [
        {"type": "function", "function": {
            "name": f.nome,
            "description": f.descricao() if callable(f.descricao) else f.descricao,
            "parameters": _aceita_null(_com_ultima_acao(f, f.parametros))}}
        for f in FERRAMENTAS.values()
        if dominios is None or f.dominio == "geral" or _dominios_de(f) & dominios
    ]


def _dominios_de(f: Ferramenta) -> set[str]:
    return {f.dominio} if isinstance(f.dominio, str) else set(f.dominio)


def frase_do_plano(acoes: list[Acao]) -> str:
    """'Vou programar o R1 para 03/10 às 14:00 e colocar o R2 aguardando
    fornecedor.' — escrita pelo CÓDIGO a partir do plano (antes era uma ida
    à IA só para isso)."""
    def ch(a):
        c = a.args.get("chamados") or []
        return ", ".join(c) if c else ""
    partes = []
    for a in acoes:
        f = a.ferramenta
        if f == "programar_atendimento":
            partes.append(f"programar o {ch(a)} para {a.args['dia']} às {a.args['hora']}")
        elif f == "resolver_chamado":
            partes.append(f"resolver o {ch(a)}")
        elif f == "aplicar_base":
            partes.append(f"aplicar a base {a.args['base']} no {ch(a)}")
        elif f == "iniciar_atendimento":
            partes.append(f"iniciar o atendimento do {ch(a)}")
        elif f == "aguardar_fornecedor":
            partes.append(f"colocar o {ch(a)} aguardando o fornecedor")
        elif f == "atribuir_chamado":
            partes.append(f"pegar o {ch(a)} para você" if a.args["para_mim"] else
                          f"atribuir o {ch(a)} a {a.args['fila']}"
                          + (f" / {a.args['tecnico']}" if a.args["tecnico"] else ""))
        elif f == "despachar_operacao":
            partes.append(f"despachar o {ch(a)} ao Serviço de Operações")
        elif f == "aguardar_usuario":
            partes.append(f"colocar o {ch(a)} aguardando o usuário")
        elif f == "info_recebida_usuario":
            partes.append(f"retomar o {ch(a)} (info recebida do usuário)")
        elif f == "info_recebida_fornecedor":
            partes.append(f"retomar o {ch(a)} (info recebida do fornecedor)")
        elif f == "adicionar_informacao":
            partes.append(f"adicionar a informação no {ch(a)}")
        elif f == "configurar_filas":
            partes.append(f"configurar a(s) fila(s) {', '.join(a.args['filas'])}")
        elif f == "desmembrar":
            partes.append(f"desmembrar o {a.args['chamado_pai']} em "
                          f"{len(a.args['tombos'])} filho(s)")
        elif f == "criar_requisicoes":
            n = len([l for l in a.args.get("texto", "").splitlines() if l.strip()])
            partes.append(f"abrir {n} requisição(ões)")
        elif f == "gerar_termo_demanda":
            partes.append(f"gerar o termo de demanda do {a.args['chamado']}")
        elif f == "gerar_termo":
            ref = f" do {a.args['chamado']}" if a.args.get("chamado") else ""
            partes.append(f"gerar o termo de responsabilidade{ref}")
        else:
            partes.append(a.titulo.lower())
    if not partes:
        return ""
    lista = partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]
    return f"Vou {lista}."


def executar(acao: Acao, sessao: Sessao) -> Resultado:
    """Roda UMA ação na sessão do plano. Erro de sessão/login vira passo com
    falha (interrompe o plano) em vez de exceção solta."""
    try:
        return FERRAMENTAS[acao.ferramenta].executar(acao.args, sessao)
    except ErroSessao as e:
        return Resultado(f"❌ {e}", ok=False)
