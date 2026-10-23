"""
services/ficha.py — A FICHA do chamado: tudo o que as ferramentas do
Assistente precisam saber de um chamado, lido UMA vez (23/10).

Antes cada ferramenta lia o chamado do seu jeito, e uma "sabia" o que a
outra não sabia (o termo de demanda não achava o local que a triagem tinha
visto). Agora:
  - `ler_ficha(page, numero, log)` abre o chamado e lê os campos da tela e a
    descrição; fica guardada por `_VALIDADE` (outra ferramenta, na mesma
    conversa, não reabre o chamado);
  - quem precisa de um dado pede à ficha, com a MESMA regra de origem:
    o técnico disse > a descrição diz (regex) > a IA entendeu do pedido >
    os campos do chamado.

O que NÃO vai para a IA: a descrição inteira, o usuário afetado (nome e
matrícula). Para a IA só `pedido` (triagem.pedido_seguro: sem o bloco de
dados pessoais) e os campos de lotação/equipamento.
"""

import dataclasses
import time

from services import triagem

_VALIDADE = 15 * 60   # s — o chamado pode mudar; 15 min cobre uma conversa
_cache: dict[str, tuple[float, "Ficha"]] = {}

# chave -> name do input na tela do chamado (captura de 10/10, R2443838)
_CAMPOS = {
    "secao": "section.text", "grupo": "department.text",
    "edificio": "building.text", "sala": "room.text",
    "item_a": "itemA.text", "item_b": "itemB.text",
    "categoria": "eventBuilder.text", "resumo": "shortDescription",
    "fila": "assignedServDept.text", "atribuido": "assignee.text",
}
# Por id fixo (sem prefixo de formulário)
_IDS = {
    "inicio_data": "#txt_scheduledStartDateDate", "inicio_hora": "#txt_scheduledStartDateTime",
    "fim_data": "#txt_scheduledEndDateDate", "fim_hora": "#txt_scheduledEndDateTime",
}


@dataclasses.dataclass
class Ficha:
    numero: str
    secao: str = ""
    grupo: str = ""
    edificio: str = ""
    sala: str = ""
    item_a: str = ""
    item_b: str = ""
    categoria: str = ""
    resumo: str = ""
    fila: str = ""
    atribuido: str = ""
    inicio_data: str = ""
    inicio_hora: str = ""
    fim_data: str = ""
    fim_hora: str = ""
    afetado_matricula: str = ""     # NÃO vai para a IA
    afetado_nome: str = ""          # NÃO vai para a IA
    tecnico_logado: str = ""
    descricao: str = ""             # inteira, com dados pessoais: NÃO vai para a IA

    # ------------------------------------------------------------------ #
    # Derivados da descrição (pelo código)
    # ------------------------------------------------------------------ #

    @property
    def pedido(self) -> str:
        """A descrição sem o bloco de dados pessoais — pode ir para a IA."""
        return triagem.pedido_seguro(self.descricao)

    @property
    def tombos(self) -> list[str]:
        return triagem.tombos_da_descricao(self.descricao)

    @property
    def local_descrito(self) -> str:
        """'Local: ...' escrito na descrição (regex do termo de demanda)."""
        from services.termos.demanda import extrair_local
        return extrair_local(self.descricao)

    @property
    def evento(self) -> str:
        """O 1º parágrafo do pedido (descrição do evento no termo)."""
        from services.termos.demanda import extrair_descricao
        return extrair_descricao(self.pedido_com_linhas) or self.pedido

    @property
    def pedido_com_linhas(self) -> str:
        """Como `pedido`, mas mantendo as quebras de linha (os extratores
        do termo trabalham por linha/parágrafo)."""
        texto = self.descricao
        m = triagem._RE_BLOCO.search(texto)
        return texto[:m.start()] if m else texto

    @property
    def local_do_chamado(self) -> str:
        """Edifício + Sala dos campos — o último recurso para 'onde é'."""
        if not self.edificio or triagem.POR_DEFINIR in triagem._chave(self.edificio):
            return ""
        sala = self.sala if self.sala and "definir" not in self.sala.lower() else ""
        return f"{self.edificio} — {sala}" if sala else self.edificio

    def para_ia(self) -> str:
        """O que a IA pode ver da ficha (sem afetado nem descrição inteira)."""
        partes = [f"{self.numero}", f"seção {self.secao or '?'}",
                  f"edifício {self.edificio or '?'}"]
        if self.sala:
            partes.append(f"sala {self.sala}")
        if self.categoria:
            partes.append(f"categoria {self.categoria}")
        if self.inicio_data:
            partes.append(f"agendado {self.inicio_data} {self.inicio_hora}"
                          f"–{self.fim_hora}".rstrip("–"))
        if self.tombos:
            partes.append(f"tombos {', '.join(self.tombos)}")
        texto = " · ".join(partes)
        return texto + (f'. Pedido: "{self.pedido}"' if self.pedido else "")


def _valor(page, seletor: str) -> str:
    try:
        campo = page.locator(f"{seletor}:visible")
        return campo.first.input_value().strip() if campo.count() else ""
    except Exception:
        return ""


def _ler(page, numero: str) -> Ficha:
    from services.assyst_common import _so_o_nome

    f = Ficha(numero=numero)
    for chave, nome in _CAMPOS.items():
        setattr(f, chave, _valor(page, f"[name='{nome}']"))
    for chave, seletor in _IDS.items():
        setattr(f, chave, _valor(page, seletor))
    bruto = _valor(page, "input[name='affectedUser.text']")
    if "(" in bruto:
        f.afetado_matricula = bruto[:bruto.find("(")].strip()
        f.afetado_nome = _so_o_nome(bruto)
    try:
        f.descricao = page.frame_locator("iframe[title*='formattedRemarks']:visible") \
            .first.locator("body").inner_text(timeout=5000)
    except Exception:
        f.descricao = ""
    try:
        f.tecnico_logado = page.locator("#userDropDownButton_label").first \
            .inner_text(timeout=2000).strip()
    except Exception:
        f.tecnico_logado = ""
    return f


def ler_ficha(pagina, numero: str, log, recente: bool = True) -> "Ficha | None":
    """A ficha do chamado (da memória se lida há menos de `_VALIDADE`).
    `pagina` = função que devolve a página logada (ex.: Sessao.pagina) — só
    é chamada se precisar abrir o Assyst. None = não abriu. `recente=False`
    força reler."""
    from services.browser_pw import _navegar_para_chamado_pw

    numero = (numero or "").strip().upper()
    if not numero:
        return None
    if recente and guardada(numero):
        return guardada(numero)
    page = pagina()
    if not _navegar_para_chamado_pw(page, numero, log):
        return None
    f = _ler(page, numero)
    _cache[numero] = (time.monotonic(), f)
    return f


def guardada(numero: str) -> "Ficha | None":
    """A ficha já lida nesta conversa, sem abrir o Assyst."""
    g = _cache.get((numero or "").strip().upper())
    return g[1] if g and time.monotonic() - g[0] < _VALIDADE else None


def esquecer(*numeros: str) -> None:
    """Joga fora a ficha: depois de uma ação que MUDA o chamado (atribuir,
    resolver...), a próxima leitura tem que ir ao Assyst."""
    for n in numeros:
        _cache.pop((n or "").strip().upper(), None)


def numeros_da_acao(args: dict) -> list[str]:
    """Os chamados de uma ação (chamados / chamado / chamado_pai)."""
    saida = []
    for chave in ("chamados", "chamado", "chamado_pai"):
        v = args.get(chave)
        saida += [str(x) for x in v] if isinstance(v, list) else ([str(v)] if v else [])
    return saida
