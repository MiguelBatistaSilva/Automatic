"""
services/agente/ferramentas/por_fila.py — Corrigir Item B e Adicionar Itom
pelo agente (16/11).

As mesmas funções do Desmembramento (modos "itemb" e "itom"), só que o
técnico diz o MÍNIMO: "corrige o Item B dos chamados do Adriano na fila do
2N CATI FCB", "adiciona o Itom nos chamados do Aureliano na Sala de Imagem".
O nome é do USUÁRIO AFETADO (não do técnico). O código lê a fila, filtra
pelo nome, abre cada chamado e decide; o cartão mostra tudo para confirmar.

- Seleção: pelos números ditos OU por fila + nome do usuário ('todos' = a
  fila inteira; Minha Fila sem nome = toda). Nomes não voltam à IA.
- Corrigir Item B: a MESMA regra da correção automática do aplicar base /
  resolver (verificacoes.item_b_a_corrigir): Item B vazio ou IC NÃO
  LOCALIZADO com tombo na descrição vira *tombo (não achado no Assyst = fica
  IC NÃO LOCALIZADO); vazio sem tombo = IC NÃO LOCALIZADO; item já escolhido
  fica.
- Adicionar Itom: tombo = o do Item B (chamado desmembrado já o tem); sem ele,
  o único da descrição.
- Execução: os fluxos de sempre (flow_corrigir_chamado_pw.corrigir_chamado,
  flow_anexo_itom_pw.gerar_pdfs/anexar), na página da Sessao. Nenhum arquivo
  de fluxo mudou. O Itom roda em outra thread (o Playwright sync não abre um
  2º navegador na mesma thread — igual ao base._itom).
"""

from concurrent.futures import ThreadPoolExecutor

from services.agente.ferramentas.base import (
    Acao,
    Ferramenta,
    _CHAMADOS,
    _lista,
    _ok_falha,
    _sem_acento,
)
from services.agente.ferramentas.investigacao import _FILA_ASSYST, _fila_pedida
from services.agente.ferramentas.verificacoes import (
    _executar_correcoes,
    item_b_a_corrigir,
    marca_correcao,
)
from services.agente.sessao import Resultado, Sessao

# ~5 s por chamado aberto: a conversa não pode ficar presa (Telegram).
_MAX_LIDOS = 30
_TODOS = {"todos", "todas", "tudo", "toda", "toda a fila", "fila toda", "fila inteira"}

_ALVO = {
    "chamados": _CHAMADOS,
    "fila": {**_FILA_ASSYST, "description": _FILA_ASSYST["description"]
             + " Use com nome quando o técnico não diz os números."},
    "nome": {"type": "string", "description":
             "Nome do usuário dos chamados na fila (o que o técnico disse), "
             "ou 'todos' (a fila inteira)."},
}


def _bate(nome_dito: str, nome: str) -> bool:
    palavras = _sem_acento(nome_dito).split()
    alvo = _sem_acento(nome or "")
    return bool(palavras) and all(p in alvo for p in palavras)


def _varias_filas(dita) -> str:
    """'Sala de Imagem' casa com duas filas: pergunta qual, em vez de dizer
    'não sei ler a fila'."""
    from services.fluxos.flow_minhafila_pw import FILAS_ASSYST, _chave_fila

    palavras = set(_chave_fila(str(dita or "")).split())
    if not palavras:
        return ""
    batem = [n for n in FILAS_ASSYST if palavras <= set(_chave_fila(n).split())]
    if len(batem) < 2:
        return ""
    return (f"'{dita}' pode ser mais de uma fila: {' ou '.join(batem)}. "
            "Pergunte ao técnico qual.")


def _selecionar(args: dict, s: Sessao) -> dict:
    """Completa args com _fichas {numero: Ficha}, _notas e _erro."""
    from services.agente.ficha import ler_ficha
    from services.fluxos.flow_minhafila_pw import MINHA_FILA, ler_fila

    notas: list[str] = []
    fichas: dict = {}

    def erro(texto: str) -> dict:
        return {**args, "_lido_do_chamado": True, "_erro": texto}

    def abrir(numero: str):
        f = ler_ficha(s.pagina, numero, s.log, recente=False)
        if f is None:
            notas.append(f"{numero}: não consegui abrir")
        return f

    chamados = [c.strip().upper() for c in _lista(args.get("chamados"))]
    if chamados:
        for n in chamados[:_MAX_LIDOS]:
            f = abrir(n)
            if f:
                fichas[n] = f
        if len(chamados) > _MAX_LIDOS:
            notas.append(f"{len(chamados)} chamados: só os {_MAX_LIDOS} primeiros")
        return {**args, "_lido_do_chamado": True, "_fichas": fichas, "_notas": notas}

    fila, e = _fila_pedida(args)
    if e:
        return erro(_varias_filas(args.get("fila")) or e)
    if not fila:
        return erro("Falta dizer os chamados ou a fila (e de qual usuário).")
    dito = str(args.get("nome") or "").strip()
    todos = not dito and fila == MINHA_FILA or _sem_acento(dito) in _TODOS
    if not dito and not todos:
        return erro(f"Na fila {fila}: os chamados de qual usuário? (ou 'todos' da fila). "
                    "Pergunte ao técnico.")

    linhas = ler_fila(s.pagina(), s.log, fila)
    if linhas is None:
        return erro(f"Não consegui ler a fila {fila} (a tela não carregou).")
    if not linhas:
        return erro(f"A fila {fila} está VAZIA. Diga isso ao técnico.")

    # O nome é do USUÁRIO AFETADO (16/11), como no buscar_chamado_por_usuario.
    escolhidos = [l["referencia"] for l in linhas
                  if todos or _bate(dito, l.get("afetado", ""))]
    if not escolhidos:
        return erro(f"Nenhum chamado de '{dito}' na fila {fila} ({len(linhas)} chamados). "
                    "Diga isso ao técnico e pergunte se é outra fila.")
    pessoas = {_sem_acento(l.get("afetado", "")) for l in linhas if l["referencia"] in escolhidos}
    if not todos and len(pessoas) > 1:
        notas.append(f"ATENÇÃO: '{dito}' bate com {len(pessoas)} pessoas diferentes; "
                     "confira os chamados antes de confirmar")

    if len(escolhidos) > _MAX_LIDOS:
        notas.append(f"{len(escolhidos)} chamados: só os {_MAX_LIDOS} primeiros")
        escolhidos = escolhidos[:_MAX_LIDOS]
    sel = {}
    for n in escolhidos:
        f = abrir(n)
        if f:
            sel[n] = f
    origem = f"{len(sel)} chamado(s) " + ("da fila " if todos else f"de {dito} na fila ") + fila
    return {**args, "_lido_do_chamado": True, "_fichas": sel, "_notas": notas,
            "_origem": origem}


def _precisa_ler(a: dict) -> bool:
    return bool(_lista(a.get("chamados")) or a.get("fila"))


def _falta(args: dict) -> "str | None":
    if not _precisa_ler(args):
        return "Falta dizer os chamados ou a fila (e de qual usuário)."
    if not args.get("_lido_do_chamado"):
        return "Não consegui ler os chamados no Assyst."
    return args.get("_erro") or None


def _cartao(titulo: str, ferramenta: str, args: dict, fazer: dict[str, str],
            linhas_fazer: list[str], fora: list[str], acao_args: dict) -> "Acao | str":
    notas = args.get("_notas") or []
    if not fazer:
        motivo = "; ".join(fora + notas) or "nenhum chamado"
        return f"Nada a fazer em {titulo}: {motivo}. Diga isso ao técnico."
    linhas = []
    if args.get("_origem"):
        linhas.append(f"**{args['_origem']}**")
    linhas.append("**Fazer:**\n" + "\n".join(f"- {l}" for l in linhas_fazer))
    if fora:
        linhas.append("**Fica de fora:**\n" + "\n".join(f"- {l}" for l in fora))
    return Acao(ferramenta=ferramenta, args={"chamados": list(fazer), **acao_args},
                titulo=titulo, linhas=linhas, escreve=True, pode_simular=True,
                aviso="; ".join(notas))


# --------------------------------------------------------------------------- #
# Corrigir Item B
# --------------------------------------------------------------------------- #

def _prep_item_b(args: dict) -> "Acao | str":
    from services.agente.triagem import IC_NAO_LOCALIZADO, sugerir_item_b

    falta = _falta(args)
    if falta:
        return falta
    fazer, linhas, fora = {}, [], []
    for n, f in (args.get("_fichas") or {}).items():
        # A MESMA regra da correção automática (verificacoes.item_b_a_corrigir).
        atual = (f.item_b or "").strip()
        b = sugerir_item_b(atual, f.descricao)
        if item_b_a_corrigir(b):
            fazer[n] = {"item_b": b.sugerido}
            linhas.append(f"{n}: Item B '{atual or 'vazio'}' → {b.sugerido} ({b.motivo})")
        elif atual == IC_NAO_LOCALIZADO:
            fora.append(f"{n}: IC NÃO LOCALIZADO e {b.motivo or 'sem tombo novo'}")
        else:
            fora.append(f"{n}: Item B já preenchido ({atual})")
    return _cartao("Corrigir Item B", "corrigir_item_b", args, fazer, linhas, fora,
                   {"correcoes": fazer})


def _exec_item_b(a: dict, s: Sessao) -> Resultado:
    feitos = _executar_correcoes(a, s)
    linhas = [f"- {marca_correcao(ok, txt)} {n} — {txt}" for n, (ok, txt) in feitos.items()]
    n_ok = sum(marca_correcao(ok, txt) == "✅" for ok, txt in feitos.values())
    sufixo = " (simulação, nada salvo)" if s.modo_teste else ""
    cab = f"**Corrigir Item B{sufixo}** — {n_ok} de {len(feitos)}."
    # Só falha de verdade (❌) interrompe o plano; ⚠️ é para escolher na mão.
    return Resultado("\n".join([cab] + linhas), ok=all(ok for ok, _ in feitos.values()))


# --------------------------------------------------------------------------- #
# Adicionar Itom (PDF da tela da máquina anexado ao chamado)
# --------------------------------------------------------------------------- #

def _prep_itom(args: dict) -> "Acao | str":
    from services.agente.triagem import tombo_do_item_b

    falta = _falta(args)
    if falta:
        return falta
    fazer, linhas, fora = {}, [], []
    for n, f in (args.get("_fichas") or {}).items():
        t = tombo_do_item_b(f.item_b)
        de = "do Item B"
        if not t and len(f.tombos) == 1:
            t, de = f.tombos[0], "da descrição"
        if t:
            fazer[n] = t[-6:]
            linhas.append(f"{n}: tombo {t[-6:]} ({de})")
        elif f.tombos:
            fora.append(f"{n}: Item B sem tombo e {len(f.tombos)} tombos na descrição")
        else:
            fora.append(f"{n}: sem tombo no Item B nem na descrição")
    return _cartao("Adicionar Itom", "anexar_itom", args, fazer, linhas, fora,
                   {"pares": fazer})


def _exec_itom(a: dict, s: Sessao) -> Resultado:
    from services.fluxos import flow_anexo_itom_pw as anexo

    linhas = [anexo.Linha(c, t) for c, t in (a.get("pares") or {}).items()]
    s.log(f"Itom: gerando {len(linhas)} PDF(s)...", "status")
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(anexo.gerar_pdfs, linhas, s.matricula, s.senha, s.log).result()
    except Exception as e:
        for l in linhas:
            if not l.situacao:
                l.situacao, l.detalhe = "erro", f"falha no Itom: {e}"
    pendentes = [l for l in linhas if l.pdf and not l.situacao]
    if pendentes:
        page = s.pagina()
        for l in pendentes:
            try:
                anexo.anexar(page, s.log, l, s.modo_teste)
            except Exception as e:
                l.situacao, l.detalhe = "erro", str(e)

    bons = ("anexado", "já anexado", "simulado")
    n_ok = sum(l.situacao in bons for l in linhas)
    sufixo = " (simulação, nada salvo)" if s.modo_teste else ""
    cab = f"**Adicionar Itom{sufixo}** — {n_ok} de {len(linhas)}."
    corpo = [f"- {_ok_falha(l.situacao in bons)} {l.chamado} · {l.tombo} · "
             f"{l.host or '—'} — {l.situacao}" + (f" ({l.detalhe})" if l.situacao == "erro" else "")
             for l in linhas]
    return Resultado("\n".join([cab] + corpo), ok=n_ok == len(linhas))


FERRAMENTAS: list[Ferramenta] = [
    Ferramenta(
        "corrigir_item_b",
        "Preenche o Item B VAZIO pelo tombo da descrição, pelos números ou por "
        "fila + nome do usuário. O sistema acha os chamados e os tombos.",
        {"type": "object", "properties": _ALVO},
        preparar=_prep_item_b, executar=_exec_item_b, antes=_selecionar,
        precisa_ler=_precisa_ler, dominio="chamados",
    ),
    Ferramenta(
        "anexar_itom",
        "ADICIONAR ITOM: anexa ao chamado o PDF da tela do Itom da máquina (tombo "
        "do Item B ou da descrição), pelos números ou por fila + nome do usuário.",
        {"type": "object", "properties": _ALVO},
        preparar=_prep_itom, executar=_exec_itom, antes=_selecionar,
        precisa_ler=_precisa_ler, dominio="chamados",
    ),
]
