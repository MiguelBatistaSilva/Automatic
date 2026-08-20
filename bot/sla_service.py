"""
bot/sla_service.py — SLA sem interface.

A orquestracao do SLA (login -> laco de chamados -> calculo) hoje so existe
dentro de state/sla_state.py, amarrada a tela do Reflex. O bot do Telegram
precisa do mesmo trabalho sem tela, entao ela mora aqui: quem chama recebe uma
lista de dicts e decide o que fazer com ela (tabela, chat, arquivo).

Este arquivo NAO substitui o sla_state — a aba do Reflex continua como esta. Se
o bot se provar, o state pode passar a chamar daqui e a duplicacao some.

SO LEITURA: abre o chamado, le o historico de acoes e calcula. Nao altera nada.
"""
from services.browser_pw import NavegadorPW, _fazer_login_pw, _usuario_afetado_pw
from services.flow_sla_pw import extrair_historico_chamado
from services.sla_engine import calcular_sla, FILAS, FILA_PADRAO


def _silencioso(msg, tipo="info"):
    pass


def analisar_chamados(chamados, fila, matricula, senha, log=None):
    """Roda a analise de ponta a ponta e devolve uma lista de dicts.

    A lista tem SEMPRE o mesmo tamanho da entrada: chamado que falhou vem com
    ok=False e o motivo, em vez de sumir. Quem le o resultado precisa conseguir
    dizer o que nao deu certo — um chamado ausente da resposta seria lido como
    "estava tudo bem".
    """
    log = log or _silencioso
    fila = fila if fila in FILAS else FILA_PADRAO
    resultados = []

    with NavegadorPW(log) as page:
        if not _fazer_login_pw(page, matricula, senha, log):
            return [
                {"numero": c, "ok": False, "erro": "Falha no login"}
                for c in chamados
            ]

        total = len(chamados)
        for i, numero in enumerate(chamados, 1):
            log(f"[{i}/{total}] Analisando {numero}...", "status")

            historico = extrair_historico_chamado(page, numero, log)
            if historico is None:
                resultados.append({
                    "numero": numero,
                    "ok": False,
                    "erro": "Nao consegui abrir o chamado ou ler o historico",
                })
                continue

            # Lido DEPOIS do historico: a essa altura o extrair_historico_chamado
            # ja confirmou que a tela aberta e a do chamado pedido.
            usuario = _usuario_afetado_pw(page)
            r = calcular_sla(historico, fila)

            resultados.append({
                "numero": numero,
                "ok": True,
                "usuario": usuario or "--",
                "fila": fila,
                "inicio": r.get("inicio", "--"),
                "tempo_gasto": r.get("tempo_gasto_str", "--"),
                "tempo_restante": r.get("tempo_restante_str", "--"),
                "estourado": r.get("estourado", False),
                "mensagem": r.get("mensagem", "--"),
                "acoes": len(historico),
            })

    return resultados
