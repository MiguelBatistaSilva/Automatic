"""
state/api_keys_state.py — Back-end da página "API Keys" (/api-keys, aberta
pelo menu Opções; era pop-up até 06/10).

Junta as chaves de serviços externos num lugar só (2026-10-02, pedido do
usuário).

GERADA PELO CATÁLOGO (08/10): um cartão por plataforma de IA de
`llm.PLATAFORMAS` (com os modelos dela, de `llm.MODELOS`) + o token do bot do
Telegram. Plataforma nova aparece aqui sozinha — antes cada chave tinha
campos e eventos escritos à mão.

  - IA (Assistente): cada técnico cadastra a SUA; sem nenhuma o Assistente
    não funciona. Cofre do Windows (services/agente/llm.py).
  - Telegram (bot): o token do @BotFather, só na máquina que roda o bot
    (bot/services/credencial_servico.py).

Nenhuma chave vai para o banco, arquivo ou git. `carregar` é o on_load da
página: lê o Cofre a cada visita (outra tela pode ter mudado a chave).
"""

import dataclasses

import reflex as rx

ROTA = "/api-keys"
TELEGRAM = "telegram"

_VERDE, _CINZA, _AMBAR, _VERMELHO = "#16A34A", "#6B7280", "#B45309", "#DC2626"


@dataclasses.dataclass
class Chave:
    id: str                # id da plataforma em llm.PLATAFORMAS, ou TELEGRAM
    nome: str
    usada_por: str         # "Assistente — GPT-OSS 120B"
    ajuda: str
    aviso: str
    link: str
    link_texto: str
    placeholder: str
    valor: str = ""
    mostrar: bool = False
    cadastrada: bool = False
    status: str = ""
    cor: str = _CINZA


def _cartoes_ia() -> list[Chave]:
    from services.agente import llm
    saida = []
    for p in llm.PLATAFORMAS.values():
        modelos = ", ".join(m.rotulo.split("·")[-1].strip()
                            for m in llm.MODELOS.values() if m.plataforma == p.id)
        valor = llm.carregar_chave(p.id)
        obrigatoria = p.id == llm.PADRAO
        saida.append(Chave(
            id=p.id, nome=p.nome, usada_por=f"Assistente — {modelos}",
            ajuda=p.ajuda, aviso=p.aviso, link=p.link, link_texto="Criar chave",
            placeholder=p.placeholder,
            valor=valor, cadastrada=bool(valor),
            # Cadastrada: sem texto — o selo "Cadastrada" já diz (08/10).
            status=("" if valor
                    else "Sem chave: este modelo fica indisponível no chat." if obrigatoria
                    else "Opcional: outro modelo para escolher no chat."),
            cor=_VERDE if valor else (_AMBAR if obrigatoria else _CINZA),
        ))
    return saida


def _cartao_telegram() -> Chave:
    from bot.services import credencial_servico
    valor = credencial_servico.carregar_token()
    return Chave(
        id=TELEGRAM, nome="Telegram", usada_por="Bot do Automatic",
        ajuda="Token do @BotFather. Só é preciso na máquina que roda o bot.",
        aviso="", link="https://t.me/BotFather", link_texto="Abrir o @BotFather",
        placeholder="dado pelo @BotFather",
        valor=valor, cadastrada=bool(valor),
        status="Token cadastrado." if valor else "Só é preciso na máquina que roda o bot.",
        cor=_VERDE if valor else _CINZA,
    )


class ApiKeysState(rx.State):
    ia: list[Chave] = []
    bot: list[Chave] = []   # lista de 1, para a página usar o mesmo cartão

    @rx.event
    def carregar(self):
        self.ia = _cartoes_ia()
        self.bot = [_cartao_telegram()]

    def _mudar(self, id_: str, **campos) -> None:
        if id_ == TELEGRAM:
            self.bot = [dataclasses.replace(c, **campos) for c in self.bot]
        else:
            self.ia = [dataclasses.replace(c, **campos) if c.id == id_ else c
                       for c in self.ia]

    def _achar(self, id_: str) -> Chave | None:
        return next((c for c in self.ia + self.bot if c.id == id_), None)

    @rx.event
    def set_valor(self, id_: str, v: str):
        self._mudar(id_, valor=v)

    @rx.event
    def alternar_mostrar(self, id_: str):
        c = self._achar(id_)
        if c:
            self._mudar(id_, mostrar=not c.mostrar)

    @rx.event
    def salvar(self, id_: str):
        c = self._achar(id_)
        if c is None:
            return
        if id_ == TELEGRAM:
            return self._salvar_telegram(c)
        return self._salvar_ia(c)

    def _salvar_ia(self, c: Chave):
        from services.agente import llm
        p = llm.PLATAFORMAS[c.id]
        chave = c.valor.strip()
        if not chave:
            self._mudar(c.id, status="Cole a chave antes de salvar.", cor=_VERMELHO)
            return
        if p.prefixo and not chave.startswith(p.prefixo):
            self._mudar(c.id, status=f"A chave da {p.nome} começa com {p.prefixo} — "
                                     "confira o que foi colado.", cor=_VERMELHO)
            return
        try:
            llm.salvar_chave(chave, c.id)
        except Exception as e:
            self._mudar(c.id, status=f"Não foi possível gravar no Cofre do Windows: {e}",
                        cor=_VERMELHO)
            return
        self._mudar(c.id, valor=chave, cadastrada=True, mostrar=False, cor=_VERDE,
                    status="Chave salva. O modelo já aparece no seletor do chat.")
        # A página do Assistente (se aberta) passa a mostrar o chat na hora.
        from state.assistente_state import AssistenteState
        return AssistenteState.on_load

    def _salvar_telegram(self, c: Chave):
        from bot.services import credencial_servico
        try:
            credencial_servico.salvar_token(c.valor)
        except ValueError as e:
            self._mudar(c.id, status=str(e), cor=_VERMELHO)
            return
        except Exception as e:
            self._mudar(c.id, status=f"Não foi possível gravar no Cofre do Windows: {e}",
                        cor=_VERMELHO)
            return
        self._mudar(c.id, cadastrada=True, mostrar=False, status="Token salvo.", cor=_VERDE)
