"""
state/despachos_state.py — Back-end da aba "Modelos de Despacho" da página
Configurações (pages/configuracoes.py), 09/11.

Edita os modelos de services/agente/conhecimento/chamados/despachos.md: os
testes e o defeito que o Assistente põe no script de despacho ao Serviço de
Operações (despachar_operacao). A IA só escolhe o modelo pelo nome; o texto
sai daqui exatamente como está escrito.

Mesma regra da aba Referência: edita só onde há `.git` (a máquina de quem
publica); nas outras, só consulta. Editou -> commit -> o updater leva a todos.
O agente lê o arquivo a cada pedido: a mudança vale na hora.
"""
import reflex as rx

TODOS = "Todos os tipos"
_VERDE, _VERMELHO, _CINZA, _LARANJA = "#16A34A", "#DC2626", "#6B7280", "#D97706"


def _tipos() -> list[str]:
    from services.agente import despacho_operacao as dop
    return list(dop.TIPOS)


def _pedidos(texto: str) -> list[str]:
    from services.agente.despacho_operacao import _chave
    return [p for p in (_chave(x) for x in (texto or "").split(",")) if p]


class DespachosState(rx.State):
    editavel: bool = False
    tipos: list[str] = []
    filtros: list[str] = []             # "Todos os tipos" + tipos
    filtro: str = TODOS
    busca: str = ""
    lista: list[dict[str, str]] = []    # visíveis: i, nome, tipo, n
    total: int = 0

    sel: int = -1                       # índice em _modelos; -1 nenhum
    novo: bool = False                  # o formulário é um modelo novo
    f_nome: str = ""
    f_tipo: str = ""
    f_pedidos: str = ""
    f_defeito: str = ""
    f_testes: str = ""                  # um teste por linha
    alterado: bool = False
    confirmar_exclusao: bool = False
    avisos: list[str] = []              # pedidos que casam com outro modelo

    status: str = ""
    status_cor: str = _VERDE

    _modelos: list[dict] = []           # nome, tipo, pedidos, defeito, testes[]

    # ------------------------------------------------------------ carga --- #
    @rx.event
    def on_load(self):
        from services.dados import referencia
        self.editavel = referencia.pode_editar()
        self.tipos = _tipos()
        self.filtros = [TODOS] + self.tipos
        self._limpar_form()
        self.status = ""
        self._carregar()

    def _carregar(self):
        from services.agente import conhecimento
        self._modelos = [
            {"nome": m.nome, "tipo": m.tipo, "pedidos": m.pedidos,
             "defeito": m.defeito, "testes": list(m.testes)}
            for m in conhecimento.despachos()]
        self._filtrar()

    def _filtrar(self):
        from services.agente.despacho_operacao import _chave
        alvo = _chave(self.busca)
        lista = []
        for i, m in enumerate(self._modelos):
            if self.filtro != TODOS and m["tipo"] != self.filtro:
                continue
            texto = " ".join([m["nome"], m["pedidos"], m["defeito"], *m["testes"]])
            if alvo and alvo not in _chave(texto):
                continue
            lista.append({"i": str(i), "nome": m["nome"], "tipo": m["tipo"],
                          "n": f"{len(m['testes'])} testes"})
        self.lista = lista
        self.total = len(self._modelos)

    @rx.event
    def set_filtro(self, v: str):
        self.filtro = v
        self._filtrar()

    @rx.event
    def set_busca(self, v: str):
        self.busca = v
        self._filtrar()

    # ------------------------------------------------------- formulário --- #
    def _limpar_form(self):
        self.sel, self.novo, self.alterado = -1, False, False
        self.f_nome = self.f_tipo = self.f_pedidos = self.f_defeito = self.f_testes = ""
        self.confirmar_exclusao = False
        self.avisos = []

    def _preso(self) -> bool:
        """Há edição não salva: não troca de modelo sem salvar ou descartar."""
        if self.alterado:
            self.status = "Salve ou descarte a edição antes de trocar de modelo."
            self.status_cor = _LARANJA
        return self.alterado

    @rx.event
    def abrir(self, i: str):
        if self._preso():
            return
        self._abrir(int(i))
        self.status = ""

    def _abrir(self, i: int):
        m = self._modelos[i]
        self._limpar_form()
        self.sel = i
        self.f_nome, self.f_tipo = m["nome"], m["tipo"]
        self.f_pedidos, self.f_defeito = m["pedidos"], m["defeito"]
        self.f_testes = "\n".join(m["testes"])
        self.status = ""
        self._conferir_pedidos()

    @rx.event
    def criar(self):
        if self._preso():
            return
        self._limpar_form()
        self.novo = True
        self.f_tipo = self.filtro if self.filtro != TODOS else ""
        self.f_nome = f"{self.f_tipo} — " if self.f_tipo else ""
        self.status = ""

    @rx.event
    def descartar(self):
        sel, novo = self.sel, self.novo
        self.alterado = False
        if novo or sel < 0:
            self._limpar_form()
        else:
            self._abrir(sel)
        self.status = "Edição descartada."
        self.status_cor = _CINZA

    def _mudou(self):
        self.alterado = True
        self.confirmar_exclusao = False

    @rx.event
    def set_f_nome(self, v: str):
        self.f_nome = v
        self._mudou()

    @rx.event
    def set_f_tipo(self, v: str):
        self.f_tipo = v
        self._mudou()
        self._conferir_pedidos()

    @rx.event
    def set_f_pedidos(self, v: str):
        self.f_pedidos = v
        self._mudou()
        self._conferir_pedidos()

    @rx.event
    def set_f_defeito(self, v: str):
        self.f_defeito = v
        self._mudou()

    @rx.event
    def set_f_testes(self, v: str):
        self.f_testes = v
        self._mudou()

    def _conferir_pedidos(self):
        """Pedido que também casa com outro modelo do mesmo tipo: a escolha
        (despacho_operacao.achar_modelo) fica ambígua e o agente pergunta."""
        avisos = []
        meus = _pedidos(self.f_pedidos)
        for j, m in enumerate(self._modelos):
            if j == self.sel or m["tipo"] != self.f_tipo:
                continue
            comuns = sorted({p for p in meus for q in _pedidos(m["pedidos"])
                             if p in q or q in p})
            if comuns:
                avisos.append(f"'{', '.join(comuns)}' também casa com "
                              f"'{m['nome']}': o agente vai perguntar qual.")
        self.avisos = avisos

    @rx.var
    def prev_testes(self) -> list[str]:
        from services.agente.despacho_operacao import itens
        return [f"- {t};" for t in itens(self.f_testes)]

    @rx.var
    def prev_defeito(self) -> str:
        d = " ".join(self.f_defeito.split()).rstrip(";.").strip()
        return f"- {d};" if d else ""

    # --------------------------------------------------------- gravação --- #
    def _bloqueado(self) -> bool:
        if not self.editavel:
            self.status = "Edição só na máquina de publicação."
            self.status_cor = _VERMELHO
        return not self.editavel

    def _erro(self, msg: str):
        self.status, self.status_cor = msg, _VERMELHO

    def _gravar(self, modelos: list[dict]) -> bool:
        from services.agente import conhecimento
        try:
            conhecimento.gravar_despachos([conhecimento.ModeloDespacho(**m)
                                           for m in modelos])
        except (OSError, ValueError) as e:
            self._erro(f"Não gravou: {e}")
            return False
        self._carregar()
        return True

    @rx.event
    def salvar(self):
        from services.agente.despacho_operacao import _chave, itens
        if self._bloqueado():
            return
        nome = " ".join(self.f_nome.split()).strip(" —-")
        testes = itens(self.f_testes)
        defeito = " ".join(self.f_defeito.split()).rstrip(";.").strip()
        if not nome:
            return self._erro("Dê um nome ao modelo (ex.: 'Mouse — scroll').")
        if self.f_tipo not in self.tipos:
            return self._erro("Escolha o tipo do equipamento.")
        if not defeito:
            return self._erro("Escreva o defeito apresentado.")
        if not testes:
            return self._erro("Escreva ao menos um teste (um por linha).")
        if any(_chave(m["nome"]) == _chave(nome)
               for j, m in enumerate(self._modelos) if j != self.sel):
            return self._erro("Já existe um modelo com esse nome.")

        modelo = {"nome": nome, "tipo": self.f_tipo,
                  "pedidos": ", ".join(dict.fromkeys(
                      p.strip() for p in self.f_pedidos.split(",") if p.strip())),
                  "defeito": defeito, "testes": testes}
        modelos = [dict(m) for m in self._modelos]
        if self.novo or self.sel < 0:
            # Entra depois do último modelo do mesmo tipo (o .md fica agrupado).
            ultimos = [j for j, m in enumerate(modelos) if m["tipo"] == self.f_tipo]
            pos = ultimos[-1] + 1 if ultimos else len(modelos)
            modelos.insert(pos, modelo)
        else:
            pos = self.sel
            modelos[pos] = modelo
        if not self._gravar(modelos):
            return
        self._abrir(pos)
        self.status = "Salvo. Já vale para o Assistente; commite para levar a todos."
        self.status_cor = _VERDE

    @rx.event
    def excluir(self):
        if self._bloqueado() or self.sel < 0 or self.novo:
            return
        if not self.confirmar_exclusao:
            self.confirmar_exclusao = True
            self.status = "Clique de novo em Excluir para confirmar."
            self.status_cor = _LARANJA
            return
        nome = self._modelos[self.sel]["nome"]
        modelos = [m for j, m in enumerate(self._modelos) if j != self.sel]
        if not self._gravar(modelos):
            return
        self._limpar_form()
        self.status = f"'{nome}' excluído. Commite para levar a todos."
        self.status_cor = _CINZA
