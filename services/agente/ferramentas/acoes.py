"""
services/agente/ferramentas/acoes.py — Ações que gravam no chamado.

Resolver e corrigir, as ações em lote (Iniciar Atendimento, Informação,
Aguardando Fornecedor/Usuário e os pares de retomada), Atribuição Interna,
Atendimento Programado com início agendado e configuração das filas.
Todas passam pelo cartão de confirmação antes de rodar.
"""

import datetime
from typing import Callable

from services.agente import agendados
from services.agente.ferramentas.base import (
    Acao,
    Ferramenta,
    _CHAMADOS,
    _FILA,
    _conferir,
    _lista,
    _lista_curta,
    _ok_falha,
)
from services.agente.ferramentas.verificacoes import (
    _EDIFICIO_DITO,
    _PAR_DA_PAUSA,
    _antes_corrigir,
    _antes_resolver,
    _com_correcoes,
    _executar_correcoes,
    _executar_retomadas,
    _pergunta_edificio,
    _retomada,
)
from services.agente.sessao import Resultado, Sessao
from services.regras.sla_engine import FILAS, FILA_PADRAO


# --------------------------------------------------------------------------- #
# Corrigir chamado (a conferência mora em verificacoes.py)
# --------------------------------------------------------------------------- #

def _prep_corrigir(args: dict) -> "Acao | str":
    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta o número do chamado."
    if not args.get("_lido_do_chamado"):
        return "Não consegui ler o chamado no Assyst para conferir."
    if args.get("_pendencias"):
        return _pergunta_edificio(args, "corrigir")
    if not args.get("_correcoes"):
        return ("Nada a corrigir: Edifício e Item B estão certos em "
                f"{_lista_curta(chamados)}. Diga isso ao técnico.")
    return Acao(
        ferramenta="corrigir_chamado",
        args={"chamados": list(args["_correcoes"]), "correcoes": args["_correcoes"]},
        titulo="Corrigir chamado",
        linhas=["**Corrigir:**\n" + "\n".join(f"- {l}" for l in args["_linhas_correcao"])],
        escreve=True,
        pode_simular=True,
    )


def _exec_corrigir(a: dict, s: Sessao) -> Resultado:
    feitos = _executar_correcoes(a, s)
    linhas = [f"- {_ok_falha(ok)} {n} — {txt}" for n, (ok, txt) in feitos.items()]
    n_ok = sum(ok for ok, _ in feitos.values())
    sufixo = " (simulação, nada salvo)" if s.modo_teste else ""
    cab = f"**Corrigir chamado{sufixo}** — {n_ok} de {len(feitos)}."
    return Resultado("\n".join([cab] + linhas), ok=n_ok == len(feitos))


# --------------------------------------------------------------------------- #
# Ações em lote nos chamados (Atendimento, Informação, Fornecedor, Usuário)
# --------------------------------------------------------------------------- #

def _prep_lote(nome: str, titulo: str, com_texto: bool):
    def preparar(args: dict) -> "Acao | str":
        chamados = _lista(args.get("chamados"))
        if not chamados:
            return "Falta a lista de chamados."
        texto = (args.get("texto") or "").strip()
        if com_texto and not texto:
            return "Falta o texto a registrar nos chamados. Pergunte ao técnico."
        linhas = [f"**Chamados:** {len(chamados)} ({_lista_curta(chamados)})"]
        if com_texto:
            linhas.append(f"**Texto:** {texto}")
        return Acao(ferramenta=nome, args={"chamados": chamados, "texto": texto},
                    titulo=titulo, linhas=linhas, escreve=True, pode_simular=True)
    return preparar


def _exec_lote(funcao: Callable, titulo: str, com_texto: bool, devolve_info: bool):
    """Roda a ação em cada chamado, na página da sessão."""
    def executar(a: dict, s: Sessao) -> Resultado:
        page = s.pagina()
        r = {}
        for numero in a["chamados"]:
            s.log(f"{titulo}: chamado {numero}...", "status")
            try:
                if com_texto:
                    saida = funcao(page, s.log, numero, a["texto"], s.modo_teste)
                else:
                    saida = funcao(page, s.log, numero, modo_teste=s.modo_teste)
                ok = saida[0] if devolve_info else saida
                r[numero] = (ok, "" if ok else "o fluxo não chegou ao fim")
            except Exception as e:  # um chamado não derruba os outros
                r[numero] = (False, str(e))
        feitos = sum(1 for v in r.values() if v[0])
        cab = f"**{titulo}{' (simulação, nada salvo)' if s.modo_teste else ''}** — {feitos} de {len(r)}."
        linhas = [cab] + [f"- {_ok_falha(v[0])} {n}" + (f" — {v[1]}" if not v[0] and v[1] else "")
                          for n, v in r.items()]
        return Resultado("\n".join(linhas), ok=feitos == len(r))
    return executar


def _exec_atendimento(a, s):
    from services.fluxos.flow_atendimento_pw import iniciar_atendimento
    return _exec_lote(iniciar_atendimento, "Iniciar Atendimento", False, False)(a, s)


def _exec_informacao(a, s):
    from services.fluxos.flow_informacao_pw import adicionar_informacao
    return _exec_lote(adicionar_informacao, "Adicionar Informação", True, True)(a, s)


def _exec_fornecedor(a, s):
    from services.fluxos.flow_fornecedor_pw import aguardar_info_fornecedor
    return _exec_lote(aguardar_info_fornecedor, "Aguardando Info do Fornecedor", True, True)(a, s)


def _exec_usuario(a, s):
    from services.fluxos.flow_usuario_pw import aguardar_info_usuario
    return _exec_lote(aguardar_info_usuario, "Aguardando Info do Usuário", True, True)(a, s)


# Retomadas do relógio (06/10): o par de cada pausa — flow_info_recebida_pw.
def _prep_recebida_usuario(args: dict) -> "Acao | str":
    r = _prep_lote("info_recebida_usuario", "Info Recebidas do Usuário", False)(args)
    if isinstance(r, Acao):
        nome = (args.get("nome") or "").strip()
        r.args["nome"] = nome
        quem = f"**{nome}**" if nome else "**NOME** (lido de cada chamado)"
        r.linhas.append("**Texto:** Pendência sanada após informações recebida do(a) "
                        f"senhor(a) {quem}, atendimento retomado.")
    return r


def _exec_recebida_usuario(a, s):
    import functools
    from services.fluxos.flow_info_recebida_pw import info_recebida_usuario
    funcao = functools.partial(info_recebida_usuario, nome=a.get("nome", ""))
    return _exec_lote(funcao, "Info Recebidas do Usuário", False, True)(a, s)


def _exec_recebida_fornecedor(a, s):
    from services.fluxos.flow_info_recebida_pw import info_recebida_fornecedor
    return _exec_lote(info_recebida_fornecedor, "Info Recebida do Fornecedor", True, True)(a, s)


def _prep_atribuir(args: dict) -> "Acao | str":
    """Atribuição Interna (21/10). Sem fila nem técnico = puxar para o técnico
    logado (o fluxo lê quem é e a fila dele do pop-up)."""
    from services.fluxos import flow_atribuicao_pw as fa

    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta a lista de chamados."
    para_mim = bool(args.get("para_mim"))
    fila, tecnico, aviso = _destino_atribuicao(args, para_mim)
    if fila is None:
        return tecnico  # a pergunta para o técnico
    if not para_mim and not fila:
        return "Falta a fila para onde o chamado vai. Pergunte (ou é para o próprio técnico?)."
    texto = (args.get("texto") or "").strip()
    motivo = (args.get("motivo") or "").strip()
    modo = args.get("modo") or (fa.LIVRE if texto else fa.PUXAR if para_mim else fa.ESCALONAR)
    if modo not in fa.MODOS:
        return f"Modo inválido: {modo}. Válidos: {', '.join(fa.MODOS)}."
    if modo == fa.ESCALONAR and not motivo:
        return "Falta o motivo do escalonamento (vai em 'Atividades realizadas'). Pergunte."
    if modo == fa.LIVRE and not texto:
        return "Falta o texto. Pergunte ao técnico."
    destino = (f"{fila or 'a fila do técnico'} / o próprio técnico" if para_mim
               else fila + (f" / {tecnico}" if tecnico else " (sem técnico)"))
    previa = {fa.ESCALONAR: f"Encaminhando para análise.\nAtividades realizadas: {motivo}",
              fa.PUXAR: "Prezado(a),\nInformo que sua solicitação encontra-se em análise. "
                        "Em breve entraremos em contato.",
              fa.CONTATO: "Contato com êxito, suporte realizando intervenção técnica.",
              fa.LIVRE: texto}[modo]
    return Acao(ferramenta="atribuir_chamado",
                args={"chamados": chamados, "fila": fila, "tecnico": tecnico,
                      "para_mim": para_mim, "modo": modo,
                      "detalhe": motivo if modo == fa.ESCALONAR else texto},
                titulo="Atribuição Interna",
                linhas=[f"**Chamados:** {len(chamados)} ({_lista_curta(chamados)})",
                        f"**Para:** {destino}",
                        f"**Texto:**\n{previa}"],
                escreve=True, pode_simular=True, aviso=aviso)


def _destino_atribuicao(args: dict, para_mim: bool) -> tuple:
    """(fila, técnico, aviso) com os nomes EXATOS do Assyst, pela referência
    (services/dados/referencia.py). Se precisar perguntar: (None, pergunta, "")."""
    from services.dados import referencia

    dita = str(args.get("fila") or "").strip()
    fila = ""
    if dita:
        achou = referencia.resolver_fila(dita)
        if achou.opcoes:
            return None, f"Fila '{dita}' ambígua: {', '.join(achou.opcoes)}. Pergunte qual.", ""
        if not achou.ok:
            return None, f"Não existe fila '{dita}' no Assyst. Pergunte o nome certo.", ""
        fila = achou.valor
    dito = "" if para_mim else str(args.get("tecnico") or "").strip()
    if not dito:
        return fila, "", ""
    achou = referencia.resolver_tecnico(dito)
    if achou.opcoes:
        return None, (f"Há mais de um técnico '{dito}': {', '.join(achou.opcoes)}. "
                      "Pergunte qual."), ""
    if not achou.ok:
        # A lista ainda não tem todas as filas: não bloqueia, o Assyst confere.
        aviso = f"'{dito}' não está na lista de técnicos: o Assyst confere o nome na hora."
        return fila, dito, aviso
    tecnico = achou.valor
    if fila:
        return fila, tecnico, ""
    dele = referencia.filas_do_tecnico(tecnico)
    if len(dele) == 1:
        return dele[0], tecnico, ""
    atual = args.get("_fila_atual") or ""
    if atual in dele:
        return atual, tecnico, ""
    if dele:
        return None, f"{tecnico} atende {' e '.join(dele)}. Pergunte em qual fila.", ""
    return None, f"Em que fila fica {tecnico}? Pergunte.", ""


def _precisa_ler_atribuir(args: dict) -> bool:
    """Técnico de várias filas e nenhuma fila dita: só aí vale ler o chamado."""
    from services.dados import referencia

    if args.get("fila") or args.get("para_mim") or not args.get("tecnico") \
            or not _lista(args.get("chamados")):
        return False
    achou = referencia.resolver_tecnico(str(args["tecnico"]))
    return achou.ok and len(referencia.filas_do_tecnico(achou.valor)) > 1


def _antes_atribuir(args: dict, s: Sessao) -> dict:
    """Lê a fila ATUAL do chamado: se o técnico estiver nela, o chamado fica
    onde está (ver _destino_atribuicao)."""
    from services.agente.ficha import ler_ficha

    chamados = _lista(args.get("chamados"))
    f = ler_ficha(s.pagina, chamados[0], s.log)
    return {**args, "_fila_atual": f.fila} if f and f.fila else args


def _exec_atribuir(a: dict, s: Sessao) -> Resultado:
    from services.fluxos import flow_atribuicao_pw as fa

    conteudo = fa.montar_texto(a["modo"], a["detalhe"])

    def funcao(page, log, numero, _texto, modo_teste):
        return fa.atribuir_interna(page, log, numero, conteudo, fila=a["fila"],
                                   tecnico=a["tecnico"], para_mim=a["para_mim"],
                                   modo_teste=modo_teste)
    return _exec_lote(funcao, "Atribuição Interna", True, True)({**a, "texto": ""}, s)


# --------------------------------------------------------------------------- #
# Configurar filas (06/10) — consulta salva do monitor; não mexe em chamado
# --------------------------------------------------------------------------- #

def _prep_config_filas(args: dict) -> "Acao | str":
    from services.fluxos.flow_config_fila_pw import COLUNAS_PADRAO, PERFIL_PADRAO
    ditas = [f.strip() for f in (args.get("filas") or []) if str(f).strip()]
    if not ditas:
        return "Falta a lista de filas a configurar."
    if not COLUNAS_PADRAO:
        return "As colunas padrão do perfil ainda não foram definidas no sistema."
    # Nome exato do banco (28/10: "2N Demais Capital" ia como dito). A lista
    # de filas veio inteira do Assyst: fora dela não passa.
    filas, avisos = [], []
    for dita in ditas:
        fila, erro = _conferir("fila", dita, avisos)
        if erro:
            return erro
        filas.append(fila)
    filas = list(dict.fromkeys(filas))
    return Acao(ferramenta="configurar_filas", args={"filas": filas}, aviso=" ".join(avisos),
                titulo="Configurar filas",
                linhas=[f"**Filas:** {len(filas)} ({_lista_curta(filas)})",
                        f"**Perfil de coluna:** {PERFIL_PADRAO} (criado na 1ª vez, "
                        "com as colunas padrão; depois reaproveitado)",
                        "*Código, Nome e Departamento = o nome de cada fila.*"],
                escreve=True, pode_simular=True)


def _exec_config_filas(a, s: Sessao) -> Resultado:
    """Perfil primeiro (garantir_perfil: cria ou reaproveita); sem ele as
    filas não têm o que usar, então a falha dele para tudo."""
    from services.fluxos.flow_config_fila_pw import PERFIL_PADRAO, configurar_fila, garantir_perfil
    page = s.pagina()
    s.log(f"Conferindo o Perfil de coluna {PERFIL_PADRAO}...", "status")
    try:
        perfil = garantir_perfil(page, s.log, s.modo_teste)
    except Exception as e:
        perfil = None
        s.log(f"Erro no Perfil de coluna: {e}", "error")
    if perfil is None:
        return Resultado(f"❌ **Perfil de coluna {PERFIL_PADRAO}** falhou — nenhuma "
                         "fila foi configurada. Veja o log.", ok=False)
    estado = {"existente": "já existia", "criado": "criado",
              "simulado": "seria criado"}[perfil]
    feitos, linhas = 0, [f"- ✅ Perfil de coluna **{PERFIL_PADRAO}** ({estado})"]
    for fila in a["filas"]:
        s.log(f"Configurando a fila {fila}...", "status")
        try:
            ok = configurar_fila(page, s.log, fila, PERFIL_PADRAO, s.modo_teste,
                                 perfil_novo=perfil == "simulado")
            erro = "" if ok else " — o fluxo não chegou ao fim"
        except Exception as e:  # uma fila não derruba as outras
            ok, erro = False, f" — {e}"
        feitos += ok
        linhas.append(f"- {_ok_falha(ok)} {fila}{erro}")
    sufixo = " (simulação, nada salvo)" if s.modo_teste else ""
    cab = f"**Configurar filas{sufixo}** — {feitos} de {len(a['filas'])}."
    return Resultado("\n".join([cab] + linhas), ok=feitos == len(a["filas"]))


# --------------------------------------------------------------------------- #
# Atendimento Programado
# --------------------------------------------------------------------------- #

def _prep_programar(args: dict) -> "Acao | str":
    from services.fluxos.flow_programar_pw import normalizar_dia, normalizar_hora

    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta o número do chamado."
    motivo = (args.get("motivo") or "").strip()
    if not args.get("dia") or not args.get("hora"):
        return "Falta o dia (dd/mm) e/ou a hora (hh:mm) do atendimento. Pergunte ao técnico."
    if not motivo:
        return "Falta o motivo da programação. Pergunte ao técnico."
    try:
        dia, hora = normalizar_dia(args["dia"]), normalizar_hora(args["hora"])
        inicio = agendados.data_do_inicio(dia, hora)
    except ValueError as e:
        return str(e)
    return Acao(
        ferramenta="programar_atendimento",
        args={"chamados": chamados, "dia": dia, "hora": hora, "motivo": motivo,
              "inicio": inicio.isoformat()},
        titulo="Atendimento Programado",
        linhas=[f"**Chamados:** {len(chamados)} ({_lista_curta(chamados)})",
                f"**Quando:** {dia} às {hora}",
                f"**Motivo:** {motivo}",
                f"**Início automático:** {inicio:%d/%m/%Y às %H:%M}",
                "*O nome do usuário afetado é lido de cada chamado.*"],
        escreve=True,
        pode_simular=True,
    )


def _exec_programar(a, s: Sessao) -> Resultado:
    from services.fluxos.flow_programar_pw import programar_atendimento
    page = s.pagina()
    feitos, linhas = 0, []
    for numero in a["chamados"]:
        s.log(f"Programando atendimento do chamado {numero}...", "status")
        try:
            ok, info = programar_atendimento(page, s.log, numero, a["dia"], a["hora"],
                                             a["motivo"], s.modo_teste)
            erro = "" if ok else " (o fluxo não chegou ao fim)"
        except Exception as e:
            ok, info, erro = False, {}, f" ({e})"
        feitos += ok
        if ok and not s.modo_teste:
            try:
                agendados.agendar(numero, datetime.datetime.fromisoformat(a["inicio"]),
                                  s.matricula, s.chat_id)
            except Exception as e:
                ok = False
                feitos -= 1
                erro = f" (programado no Assyst, mas o início automático NÃO foi agendado: {e})"
        quem = f" — {info['usuario']}" if info.get("usuario") else ""
        linhas.append(f"- {_ok_falha(ok)} {numero}{quem}{erro}")
    sufixo = " (simulação, nada salvo)" if s.modo_teste else ""
    cab = (f"**Atendimento Programado{sufixo}** — {feitos} de {len(a['chamados'])}, "
           f"para {a['dia']} às {a['hora']}.")
    rodape = [] if s.modo_teste or not feitos else [
        f"Inicia sozinho na hora marcada, com o app ou o bot aberto. Passados {agendados._TOLERANCIA_MIN} "
        "min sem nenhum deles aberto, não inicia mais."]
    return Resultado("\n".join([cab] + linhas + rodape), ok=feitos == len(a["chamados"]))


def _prep_consultar_agendados(args: dict) -> "Acao | str":
    return Acao(ferramenta="consultar_agendados", args={}, titulo="Inícios agendados",
                linhas=[], escreve=False, assyst=False)


_NOME_STATUS = {agendados.CONCLUIDO: "✅", agendados.ERRO: "❌", agendados.CANCELADO: "🚫"}


def _exec_consultar_agendados(a, s: Sessao) -> Resultado:
    pendentes, encerrados = agendados.listar(s.matricula)
    if not pendentes and not encerrados:
        return Resultado("Nenhum início agendado.")
    linhas = ["**Inícios agendados**"]
    linhas += [f"- {t['chamado']} — {t['quando']}"
               + (" (iniciando agora)" if t["status"] == agendados.EXECUTANDO else "")
               for t in pendentes] or ["- nenhum pendente"]
    if encerrados:
        linhas.append("**Últimos encerrados**")
        linhas += [f"- {_NOME_STATUS.get(t['status'], '')} {t['chamado']} ({t['quando']}): {t['detalhe']}"
                   for t in encerrados]
    return Resultado("\n".join(linhas))


def _prep_cancelar_agendado(args: dict) -> "Acao | str":
    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta o número do chamado."
    return Acao(
        ferramenta="cancelar_agendado",
        args={"chamados": chamados},
        titulo="Cancelar início agendado",
        linhas=[f"**Chamados:** {len(chamados)} ({_lista_curta(chamados)})",
                "*No Assyst, o chamado continua em Atendimento Programado.*"],
        escreve=True,
        assyst=False,
    )


def _exec_cancelar_agendado(a, s: Sessao) -> Resultado:
    if s.modo_teste:
        return Resultado("**Cancelar início agendado (simulação, nada salvo)**")
    feitos = agendados.cancelar(a["chamados"], s.matricula)
    faltam = [n for n in a["chamados"] if n.strip().upper() not in feitos]
    linhas = [f"- {_ok_falha(True)} {n}" for n in feitos]
    linhas += [f"- {_ok_falha(False)} {n} (não está agendado)" for n in faltam]
    return Resultado("\n".join(["**Início agendado cancelado**"] + linhas), ok=not faltam)


# --------------------------------------------------------------------------- #
# Resolver chamado (2026-10-01)
# --------------------------------------------------------------------------- #

def _prep_resolver(args: dict) -> "Acao | str":
    chamados = _lista(args.get("chamados"))
    if not chamados:
        return "Falta o número do chamado."
    procedimentos = (args.get("procedimentos") or "").strip()
    if not procedimentos:
        return "Faltam os procedimentos realizados (vão no texto da resolução). Pergunte."
    fila = args.get("fila") or FILA_PADRAO
    if fila not in FILAS:
        return f"Fila desconhecida: '{fila}'. Filas válidas: {', '.join(FILAS)}."
    retomar = _retomada(args)
    if isinstance(retomar, str):
        return retomar
    r = _com_correcoes(Acao(
        ferramenta="resolver_chamado",
        args={"chamados": chamados, "procedimentos": procedimentos, "fila": fila},
        titulo="Resolver chamado",
        linhas=[f"**Chamados:** {len(chamados)} ({_lista_curta(chamados)})",
                f"**Procedimentos:**\n{procedimentos}"],
        escreve=True,
        pode_simular=True,
    ), args, "resolver")
    if isinstance(r, Acao) and retomar:
        r.args["retomar"] = retomar
        r.linhas.insert(1, "**Retomar antes:**\n" + "\n".join(
            f"- {n}: {p} → {_PAR_DA_PAUSA[p]}" for n, p in retomar.items()))
    return r


def _exec_resolver(a, s: Sessao) -> Resultado:
    from services.fluxos.flow_resolver_pw import resolver_chamado
    # Retoma e corrige antes (30/10): se um dos dois falhar, não resolve.
    retomadas = _executar_retomadas(a, s)
    correcoes = _executar_correcoes(a, s)
    page = s.pagina()
    feitos, linhas = 0, []
    for numero in a["chamados"]:
        ret = retomadas.get(numero.strip().upper())
        if ret and not ret[0]:
            linhas.append(f"- {_ok_falha(False)} {numero} — NÃO resolvido: '{ret[1]}' falhou")
            continue
        if ret:
            linhas.append(f"- Retomado {numero} — {ret[1]}")
            if s.modo_teste:
                # A retomada simulada não salva: sem ela o Assyst não mostra
                # 'Resolvido', então simular o resto só daria erro falso.
                linhas.append(f"- {numero} — Resolver não simulado: depende da retomada salva")
                continue
        corr = correcoes.get(numero.strip().upper())
        if corr and not corr[0]:
            linhas.append(f"- {_ok_falha(False)} {numero} — NÃO resolvido: {corr[1]}")
            continue
        if corr:
            linhas.append(f"- Corrigido {numero} — {corr[1]}")
        s.log(f"Resolvendo o chamado {numero}...", "status")
        try:
            ok, info = resolver_chamado(page, s.log, numero, a["procedimentos"],
                                        a["fila"], s.modo_teste)
        except Exception as e:
            ok, info = False, {"erro": str(e)}
        feitos += ok
        if info.get("estourado"):
            motivo = f" — NÃO resolvido: SLA {info['sla']}"
        elif not ok:
            motivo = f" — {info.get('erro', 'o fluxo não chegou ao fim')}"
        else:
            motivo = f" — {info.get('usuario', '')}"
        linhas.append(f"- {_ok_falha(ok)} {numero}{motivo}")
    sufixo = " (simulação, nada salvo)" if s.modo_teste else ""
    cab = f"**Resolver chamado{sufixo}** — {feitos} de {len(a['chamados'])}."
    return Resultado("\n".join([cab] + linhas), ok=feitos == len(a["chamados"]))


# Catálogo deste arquivo (o __init__ junta todos, na ordem de _ORDEM).
FERRAMENTAS: list[Ferramenta] = [
    Ferramenta(
        "resolver_chamado",
        "Resolve o chamado (ação 'Resolvido'); o sistema monta o texto da auditoria.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "procedimentos": {"type": "string", "description":
                "Ditos pelo técnico, no formato de Procedimentos da base."},
            "fila": _FILA,
            "edificio": _EDIFICIO_DITO,
            "retomar": {"type": "boolean", "description":
                        "Só quando o sistema avisar que está pausado e o técnico "
                        "autorizar retomar antes."},
        }, "required": ["chamados", "procedimentos"]},
        # Confere relógio, Edifício e Item B antes de resolver (30/10).
        preparar=_prep_resolver, executar=_exec_resolver, antes=_antes_resolver,
        dominio="chamados",
    ),
    Ferramenta(
        "corrigir_chamado",
        "Corrige Edifício e Item B do chamado pela triagem (o sistema lê e decide "
        "o valor). Resolver e aplicar base já corrigem sozinhos.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "edificio": _EDIFICIO_DITO,
        }, "required": ["chamados"]},
        preparar=_prep_corrigir, executar=_exec_corrigir, antes=_antes_corrigir,
        precisa_ler=lambda a: bool(_lista(a.get("chamados"))),
        dominio="chamados",
    ),
    Ferramenta(
        "iniciar_atendimento",
        "Inicia o atendimento agora (ação 'Iniciar Atendimento').",
        {"type": "object", "properties": {"chamados": _CHAMADOS}, "required": ["chamados"]},
        preparar=_prep_lote("iniciar_atendimento", "Iniciar Atendimento", False),
        executar=_exec_atendimento,
        dominio="chamados",
    ),
    Ferramenta(
        "programar_atendimento",
        "Agenda o atendimento para dia/hora combinados (ação 'Atendimento "
        "Programado') e o sistema inicia sozinho na hora marcada; não é "
        "iniciar_atendimento, que inicia agora.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            # Fora de `required`: obrigatórios, a IA inventava a hora (05/11). O
            # _prep_programar é quem pede o que faltar.
            "dia": {"type": "string", "description": "dd/mm. Só se o técnico disser: nunca deduza."},
            "hora": {"type": "string", "description": "hh:mm. Só se o técnico disser: nunca deduza."},
            "motivo": {"type": "string", "description": "Só se o técnico disser: nunca deduza."},
        }, "required": ["chamados"]},
        preparar=_prep_programar, executar=_exec_programar,
        dominio="chamados",
    ),
    Ferramenta(
        "consultar_agendados",
        "Mostra os inícios automáticos agendados e como terminaram os últimos.",
        {"type": "object", "properties": {}},
        preparar=_prep_consultar_agendados, executar=_exec_consultar_agendados,
        dominio="chamados",
    ),
    Ferramenta(
        "cancelar_agendado",
        "Cancela o início automático. Não muda o chamado no Assyst.",
        {"type": "object", "properties": {"chamados": _CHAMADOS}, "required": ["chamados"]},
        preparar=_prep_cancelar_agendado, executar=_exec_cancelar_agendado,
        dominio="chamados",
    ),
    Ferramenta(
        "adicionar_informacao",
        "Registra um texto nos chamados (ação 'Adicionar Informação').",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {"type": "string"}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("adicionar_informacao", "Adicionar Informação", True),
        executar=_exec_informacao,
        dominio="chamados",
    ),
    Ferramenta(
        "aguardar_fornecedor",
        "PAUSA: 'Aguardando Info do Fornecedor', com um texto.",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {"type": "string"}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("aguardar_fornecedor", "Aguardando Info do Fornecedor", True),
        executar=_exec_fornecedor,
        dominio="chamados",
    ),
    Ferramenta(
        "atribuir_chamado",
        "ATRIBUIÇÃO INTERNA: passa o chamado para uma fila (com ou sem técnico) "
        "ou o técnico puxa para si (para_mim). Não mexe no SLA.",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "para_mim": {"type": "boolean", "description":
                         "true = o técnico vai resolver ele mesmo (puxar/pegar para si)."},
            "fila": {"type": "string", "description":
                     "Departamento de destino (ex.: FCB, TJ, Remoto, Polo Iguatu)."},
            "tecnico": {"type": "string", "description": "Nome do técnico de destino, se dito."},
            "modo": {"type": "string", "enum": ["escalonar", "puxar", "contato", "livre"],
                     "description": "Texto padrão; ver chamados/atribuicao."},
            "motivo": {"type": "string", "description":
                       "escalonar: por que o técnico não resolveu (o que já fez)."},
            "texto": {"type": "string", "description": "livre: o texto ditado pelo técnico."},
        }, "required": ["chamados"]},
        preparar=_prep_atribuir, executar=_exec_atribuir, antes=_antes_atribuir,
        precisa_ler=_precisa_ler_atribuir,
        dominio="chamados",
    ),
    Ferramenta(
        "aguardar_usuario",
        "PAUSA: 'Aguardando Info do Usuário' (feito, falta o usuário testar); "
        "o sistema monta o texto da auditoria.",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {
            "type": "string",
            "description": "Procedimentos ditos pelo técnico, no formato de Procedimentos da base."}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("aguardar_usuario", "Aguardando Info do Usuário", True),
        executar=_exec_usuario,
        dominio="chamados",
    ),
    Ferramenta(
        "info_recebida_usuario",
        "RETOMADA: 'Info Recebidas do Usuário *' (texto fixo, montado pelo sistema).",
        {"type": "object", "properties": {
            "chamados": _CHAMADOS,
            "nome": {"type": "string", "description":
                     "Só se o técnico disser OUTRO nome para o texto (quem passou a "
                     "informação). Sem isso, vai o usuário do chamado."},
        }, "required": ["chamados"]},
        preparar=_prep_recebida_usuario,
        executar=_exec_recebida_usuario,
        dominio="chamados",
    ),
    Ferramenta(
        "info_recebida_fornecedor",
        "RETOMADA: 'Info Recebida do Fornecedor', com um texto.",
        {"type": "object", "properties": {"chamados": _CHAMADOS, "texto": {"type": "string"}},
         "required": ["chamados", "texto"]},
        preparar=_prep_lote("info_recebida_fornecedor", "Info Recebida do Fornecedor", True),
        executar=_exec_recebida_fornecedor,
        dominio="chamados",
    ),
    Ferramenta(
        "configurar_filas",
        "Configura filas no Assyst (consulta no menu, com o perfil de colunas "
        "padrão). Não mexe em chamados.",
        {"type": "object", "properties": {
            "filas": {"type": "array", "items": {"type": "string"},
                      "description": "Como o técnico disse; o sistema acha o nome exato."},
        }, "required": ["filas"]},
        preparar=_prep_config_filas, executar=_exec_config_filas,
        dominio="filas",
    ),
]
