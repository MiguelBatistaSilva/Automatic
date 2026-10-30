"""
services/fluxos/flow_corrigir_chamado_pw.py — Corrige campos de um chamado JÁ
SALVO (30/10): Edifício e Item B, o que o técnico confere ao pegar o chamado
(ver services/agente/triagem.py). Usado pelo Assistente antes de resolver ou
aplicar base, e sozinho ("corrige o chamado X").

Reconhecimento em simulação (30/10, S2503433, nada salvo):
  - A tela do chamado usa os MESMOS ids da tela de Requisição
    (`ManageEventForm_<P>_building_textNode`...), então os preenchimentos do
    flow_requisicao_pw servem aqui. O prefixo varia (EC119 nesse dia) e pode
    haver mais de um formulário no DOM: vale o que tem o Edifício VISÍVEL.
  - ITEM B: com o Produto B em "A ser definido", o '*tombo' NÃO acha nada
    (a busca fica presa a esse Produto). Limpando o Produto B antes (o Item B
    vai junto), '*332154' resolveu sozinho. Não achou -> IC NÃO LOCALIZADO,
    a mesma rede do fluxo de Requisição.
  - EDIFÍCIO por último: trocar Produto apaga o Item e, segundo o usuário,
    pode devolver o Edifício para "Por definir". Hoje o Produto não é mexido,
    mas a ordem já fica certa.
  - Salvar = '#btlogEvent' (o mesmo do Desmembramento). A confirmação é o
    sinal real: reabre o chamado e confere os campos gravados.

modo_teste: preenche, NÃO salva e recarrega a página para descartar.
"""

import time

from services.assyst.browser_pw import _aguardar_pagina_assentar, _navegar_para_chamado_pw
from services.fluxos.flow_requisicao_pw import (
    _ITEM_B_NAO_LOCALIZADO, _preencher_item_b, _valor_de, selecionar_lookup,
)
from services.regras.requisicao_campos import POR_CHAVE, descobrir_prefixos, id_campo

_SEL_SALVAR = "#btlogEvent"


def _prefixo(page, timeout_s: float = 15.0) -> str | None:
    """Prefixo do formulário do chamado aberto (o que tem o Edifício visível)."""
    fim = time.monotonic() + timeout_s
    while time.monotonic() < fim:
        for p in descobrir_prefixos(page):
            if page.locator(f"{id_campo(p, POR_CHAVE['edificio'])}:visible").count():
                return p
        page.wait_for_timeout(300)
    return None


def item_b_ja_certo(atual: str, alvo: str) -> bool:
    """O Item B já atende ao pedido? '*332154' casa com 'FJE06JECC332154'. IC
    NÃO LOCALIZADO nunca passa por cima de um item de verdade."""
    atual = (atual or "").strip()
    if alvo.startswith("*"):
        return bool(atual) and alvo.lstrip("*") in atual
    if alvo == _ITEM_B_NAO_LOCALIZADO:
        return bool(atual)
    return atual.lower() == alvo.lower()


def _limpar_produto_b(page, log, prefixo) -> None:
    campo = POR_CHAVE["produto_b"]
    caixa = page.locator(id_campo(prefixo, campo)).first
    caixa.click()
    caixa.press("Control+a")
    caixa.press("Delete")
    caixa.press("Tab")
    # O Assyst limpa o Item B junto; espera isso acontecer antes de digitar.
    fim = time.monotonic() + 5
    while time.monotonic() < fim and _valor_de(page, prefixo, POR_CHAVE["item_b"]):
        page.wait_for_timeout(200)
    page.wait_for_timeout(800)
    log("Produto B limpo (senão o *tombo não é encontrado).", "info")


def _preencher(page, log, prefixo, edificio: str, item_b: str) -> dict:
    """Preenche o que precisa. Devolve {campo: (antes, depois)} do que mudou;
    levanta RuntimeError se um campo não aceitar o valor."""
    mudou = {}
    if item_b:
        campo = POR_CHAVE["item_b"]
        antes = _valor_de(page, prefixo, campo)
        if item_b_ja_certo(antes, item_b):
            log(f"Item B já está certo ({antes}).", "info")
        else:
            if item_b.startswith("*"):
                _limpar_produto_b(page, log, prefixo)
            if not _preencher_item_b(page, log, prefixo, campo, item_b):
                raise RuntimeError(f"o Item B não aceitou {item_b!r}")
            depois = _valor_de(page, prefixo, campo)
            # Tombo não localizado e já estava IC NÃO LOCALIZADO: o valor é
            # válido, não há o que salvar.
            if depois != antes:
                mudou["Item B"] = (antes, depois)
            else:
                log(f"Tombo {item_b} não localizado; Item B continua {antes}.", "info")
    if edificio:
        campo = POR_CHAVE["edificio"]
        antes = _valor_de(page, prefixo, campo)
        if not selecionar_lookup(page, log, prefixo, campo, edificio):
            raise RuntimeError(f"o Edifício não aceitou {edificio!r}")
        depois = _valor_de(page, prefixo, campo)
        if depois.lower() != edificio.lower():
            raise RuntimeError(f"o Edifício ficou {depois!r}, não {edificio!r}")
        if depois != antes:
            mudou["Edifício"] = (antes, depois)
    return mudou


def _dialogo_visivel(page) -> str:
    try:
        d = page.locator(".dijitDialog:visible")
        return d.first.inner_text(timeout=1000).strip()[:300] if d.count() else ""
    except Exception:
        return ""


def corrigir_chamado(page, log, numero: str, edificio: str = "", item_b: str = "",
                     modo_teste: bool = False) -> tuple[bool, dict]:
    """(ok, info). info: 'mudou' {rótulo: (antes, depois)}, 'erro', 'simulado'.
    ok=True também quando não havia nada a mudar."""
    info: dict = {"mudou": {}}
    if not _navegar_para_chamado_pw(page, numero, log):
        return False, {**info, "erro": "não consegui abrir o chamado"}
    prefixo = _prefixo(page)
    if not prefixo:
        return False, {**info, "erro": "a tela do chamado não carregou os campos"}

    try:
        info["mudou"] = _preencher(page, log, prefixo, edificio, item_b)
    except RuntimeError as e:
        page.reload()  # descarta o que ficou pela metade
        _aguardar_pagina_assentar(page)
        return False, {**info, "erro": str(e)}

    if not info["mudou"]:
        log(f"{numero}: nada a corrigir.", "success")
        page.reload()  # o Produto B pode ter sido limpo na tentativa do tombo
        _aguardar_pagina_assentar(page)
        return True, info

    if modo_teste:
        log(f"{numero}: correção preenchida e NÃO salva (simulação).", "success")
        page.reload()
        _aguardar_pagina_assentar(page)
        return True, {**info, "simulado": True}

    try:
        page.click(_SEL_SALVAR, timeout=20000)
    except Exception as e:
        return False, {**info, "erro": f"não consegui clicar em Salvar: {e}"}
    _aguardar_pagina_assentar(page)
    page.wait_for_timeout(1500)
    dialogo = _dialogo_visivel(page)
    if dialogo:
        # Nada é clicado num diálogo desconhecido: o técnico vê e decide.
        return False, {**info, "erro": f"o Assyst abriu um aviso ao salvar: {dialogo}"}

    # Sinal real: reabre e confere o que ficou gravado.
    if not _navegar_para_chamado_pw(page, numero, log) or not (prefixo := _prefixo(page)):
        return False, {**info, "erro": "salvei, mas não consegui reabrir para conferir"}
    # Confere contra o que ficou NA TELA antes de salvar (o '*tombo' pode ter
    # virado IC NÃO LOCALIZADO, e isso não é falha).
    chaves = {"Edifício": "edificio", "Item B": "item_b"}
    faltou = [rotulo for rotulo, (_, depois) in info["mudou"].items()
              if _valor_de(page, prefixo, POR_CHAVE[chaves[rotulo]]) != depois]
    if faltou:
        return False, {**info, "erro": f"depois de salvar, {' e '.join(faltou)} não ficou gravado"}
    log(f"{numero}: correção salva e conferida.", "success")
    return True, info
