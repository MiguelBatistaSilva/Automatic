"""
services/triagem.py — O Assistente olhando o chamado COMO TÉCNICO (22/10).

Regras de triagem no CÓDIGO (a IA só recebe o resultado):
  - Edifício: "Por definir" (ou vazio) -> o edifício sai da Seção do usuário,
    pelo histórico do data/referencia/edificios.csv.
  - Item B: o tombo vem da descrição ("máquina de tombo 332244") -> o técnico
    digita *332244 + TAB no Item B; sem tombo, ou com vários (desmembrar
    depois) -> IC NÃO LOCALIZADO.

A descrição INTEIRA não sai daqui: a IA recebe os tombos achados nela e o
PEDIDO (pedido_seguro: sem o bloco automático de dados pessoais do fim, com
e-mail/CPF/telefone mascarados — decisão do usuário em 22/10).
Nada aqui chuta: sem certeza, devolve as opções para o técnico escolher.
"""

import dataclasses
import re
import unicodedata
from collections import Counter

from services import referencia

POR_DEFINIR = "por definir"
IC_NAO_LOCALIZADO = "IC NÃO LOCALIZADO"
_EXTERNO = "externo"
_DOMINANTE = 0.75   # 75% dos chamados da seção no mesmo edifício = sugere


def _chave(s: str) -> str:
    t = unicodedata.normalize("NFD", (s or "").lower())
    return " ".join("".join(c for c in t if unicodedata.category(c) != "Mn").split())


# --------------------------------------------------------------------------- #
# Edifício
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class Edificio:
    atual: str
    sugerido: str = ""          # preenchido = dá para sugerir
    motivo: str = ""            # "17 de 17 chamados da seção", "pela cidade da fila"...
    opcoes: list[str] = dataclasses.field(default_factory=list)  # ambíguo

    @property
    def por_definir(self) -> bool:
        return not self.atual or POR_DEFINIR in _chave(self.atual)


def _cidades(*textos: str) -> list[str]:
    """Cidade de 'COMARCA DE CRATEUS' (seção) e de '2N CATI Polo Crateús' (fila)."""
    saida = []
    for t in textos:
        m = re.search(r"\b(?:comarca de|polo)\s+(.+)$", _chave(t))
        # Fortaleza tem dezenas de edifícios: a cidade não desempata.
        if m and m[1].strip() != "fortaleza":
            saida.append(m[1].strip())
    return saida


def _contagem(secao: str, grupo: str) -> Counter:
    linhas = [l for l in referencia.edificios() if _chave(l["secao"]) == _chave(secao)]
    do_grupo = [l for l in linhas if grupo and _chave(l["grupo"]) == _chave(grupo)]
    cont: Counter = Counter()
    for l in do_grupo or linhas:
        cont[l["edificio"]] += int(l.get("qtd") or 1)
    return cont


def sugerir_edificio(secao: str, grupo: str = "", atual: str = "", fila: str = "") -> Edificio:
    r = Edificio(atual=atual)
    cont = _contagem(secao, grupo)
    total = sum(cont.values())
    # "Externo" em minoria é ruído (chamado atendido fora, uma vez).
    if len(cont) > 1:
        ext = [e for e in cont if _chave(e) == _EXTERNO]
        if ext and cont[ext[0]] / total < _DOMINANTE:
            total -= cont.pop(ext[0])
    if cont:
        topo, n = cont.most_common(1)[0]
        if n / total >= _DOMINANTE:
            r.sugerido, r.motivo = topo, f"{n} de {total} chamados da seção"
            return r
    # Seção ambígua (ou nova): a cidade desempata — primeiro a do nome da
    # seção, depois a da fila (um Polo atende várias comarcas). O Fórum da
    # cidade entra como candidato mesmo fora do histórico da seção (Lanlink
    # em Crateús pode ser o Fórum ou o NAC).
    for origem, texto in (("seção", secao), ("fila", fila)):
        if not cont and origem == "fila":
            break  # seção nova: a fila sozinha não basta
        for c in _cidades(texto):
            batem = [e for e in cont if c in _chave(e)]
            batem += [f for f in _foruns(c) if f not in batem]
            if len(batem) == 1:
                r.sugerido, r.motivo = batem[0], f"pela cidade da {origem}; confirme"
                return r
            if batem:
                r.opcoes = sorted(batem, key=lambda e: -cont.get(e, 0))
                return r
    r.opcoes = [e for e, _ in cont.most_common(6)]
    return r


def _foruns(cidade: str) -> list[str]:
    """'Fórum da Comarca de <cidade>', se esse edifício já apareceu no histórico."""
    return sorted({l["edificio"] for l in referencia.edificios()
                   if _chave(l["edificio"]) == f"forum da comarca de {cidade}"})


# --------------------------------------------------------------------------- #
# Item B (tombo)
# --------------------------------------------------------------------------- #

# "tombo 332244", "tombos: 332244, 332245 e 332246", "patrimônio nº 332244",
# "pat. 332244", "*332244". Só números PERTO da palavra: número solto pode ser
# telefone, matrícula ou CPF.
_RE_GATILHO = re.compile(r"tomb\w*|patrim\w*|\bpat\b\.?|\*(?=\d)", re.I)
_RE_NUMERO = re.compile(r"(?<![\d.\-/])\d{5,7}(?![\d.\-/])")
_RE_CORTE = re.compile(r"[.;:]\s+[A-Za-zÀ-ú]|\n\s*\n")


def tombos_da_descricao(texto: str) -> list[str]:
    achados: list[str] = []
    for m in _RE_GATILHO.finditer(texto or ""):
        trecho = texto[m.end():m.end() + 80]
        corte = _RE_CORTE.search(trecho)
        for n in _RE_NUMERO.findall(trecho[:corte.start()] if corte else trecho):
            if n not in achados:
                achados.append(n)
    return achados


@dataclasses.dataclass
class ItemB:
    atual: str
    tombos: list[str]
    sugerido: str = ""          # o que digitar no Item B ("" = deixar)
    motivo: str = ""


def sugerir_item_b(atual: str, descricao: str) -> ItemB:
    tombos = tombos_da_descricao(descricao)
    r = ItemB(atual=atual, tombos=tombos)
    vazio = not atual.strip()
    if len(tombos) == 1:
        if tombos[0] in atual:
            r.motivo = "Item B já é o tombo da descrição"
        else:
            r.sugerido = f"*{tombos[0]}"
            r.motivo = f"tombo {tombos[0]} na descrição (se não achar: {IC_NAO_LOCALIZADO})"
    elif len(tombos) > 1:
        if vazio:
            r.sugerido = IC_NAO_LOCALIZADO
        r.motivo = f"{len(tombos)} tombos na descrição: desmembrar um chamado por tombo"
    elif vazio:
        r.sugerido = IC_NAO_LOCALIZADO
        r.motivo = "sem tombo na descrição: coletar no atendimento e desmembrar se for mais de um"
    return r


# --------------------------------------------------------------------------- #
# O PEDIDO do usuário (a descrição sem os dados pessoais) — 22/10
# --------------------------------------------------------------------------- #
#
# Todo chamado aberto pelo portal recebe NO FIM um bloco automático com os
# dados do usuário ("Matrícula: 6129 Cargo Efetivo: Nome: ... Telefone ...
# Email ..."). Decisão do usuário (22/10): a IA pode ler o pedido, sem esse
# bloco. Corta no primeiro marcador do bloco e ainda mascara e-mail, CPF e
# telefone que o usuário tenha escrito no texto livre. Nome próprio no texto
# livre ("falar com a Maria") NÃO é detectado.

_RE_BLOCO = re.compile(
    r"\bMatr[íi]cula\s*:|\bCPF\s*:|\bNome\s*:|\bData de Nascimento|\bSetor de Lota",
    re.I)
_MASCARAS = (
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[e-mail]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[cpf]"),
    (re.compile(r"\(?\b\d{2}\)?[\s-]*9?\d{4}[\s-]?\d{4}\b"), "[telefone]"),
    (re.compile(r"\b\d{8,}\b"), "[número]"),
    (re.compile(r"\b(ramal|tel\w*|fone|celular|whats\w*|contato)\s*:?\s*[\d\s()-]{3,}", re.I),
     r"\1 [número] "),
)
_LIMITE_PEDIDO = 600


def pedido_seguro(texto: str) -> str:
    """A descrição até o bloco automático, com e-mail/CPF/telefone mascarados."""
    t = texto or ""
    m = _RE_BLOCO.search(t)
    if m:
        t = t[:m.start()]
    for padrao, troca in _MASCARAS:
        t = padrao.sub(troca, t)
    t = " ".join(t.split())
    return t[:_LIMITE_PEDIDO] + ("…" if len(t) > _LIMITE_PEDIDO else "")


# --------------------------------------------------------------------------- #
# Chamado inteiro
# --------------------------------------------------------------------------- #

@dataclasses.dataclass
class Triagem:
    chamado: str
    secao: str
    edificio: Edificio
    item_b: ItemB
    pedido: str = ""            # pedido_seguro(descrição)

    def correcoes(self) -> dict[str, str]:
        """Campo -> valor novo, só o que tem sugestão CERTA."""
        c = {}
        if self.edificio.por_definir and self.edificio.sugerido:
            c["edificio"] = self.edificio.sugerido
        if self.item_b.sugerido:
            c["item_b"] = self.item_b.sugerido
        return c

    def resumo(self) -> str:
        """Texto para a IA: seção, edifício, Item B, tombos e o pedido SEM o
        bloco de dados pessoais."""
        e, b = self.edificio, self.item_b
        if not e.por_definir:
            ed = f"Edifício OK ({e.atual})"
            if e.sugerido and _chave(e.sugerido) != _chave(e.atual):
                ed += f"; obs.: a seção costuma ser {e.sugerido} ({e.motivo})"
        elif e.sugerido:
            ed = f"Edifício Por definir -> {e.sugerido} ({e.motivo})"
        elif e.opcoes:
            ed = f"Edifício Por definir; seção ambígua, opções: {' | '.join(e.opcoes)}"
        else:
            ed = "Edifício Por definir; seção sem histórico: perguntar ao técnico"
        ib = f"Item B '{b.atual or 'vazio'}'"
        if b.sugerido:
            ib += f" -> {b.sugerido}"
        if b.motivo:
            ib += f" ({b.motivo})"
        if b.tombos:
            ib += f". Tombos: {', '.join(b.tombos)}"
        pedido = f' Pedido: "{self.pedido}"' if self.pedido else ""
        return f"{self.chamado} (seção {self.secao or '?'}): {ed}. {ib}.{pedido}"


def triar(chamado: str, campos: dict, descricao: str) -> Triagem:
    """`campos`: secao, grupo, edificio, item_b, fila — lidos da tela."""
    return Triagem(
        chamado=chamado,
        secao=campos.get("secao", ""),
        edificio=sugerir_edificio(campos.get("secao", ""), campos.get("grupo", ""),
                                  campos.get("edificio", ""), campos.get("fila", "")),
        item_b=sugerir_item_b(campos.get("item_b", ""), descricao),
        pedido=pedido_seguro(descricao),
    )
