"""
bot/agenda.py — os agendamentos do Iniciar Atendimento, gravados em disco.

POR QUE EM DISCO: um agendamento vive entre o pedido e a hora marcada, as vezes
por horas. Se ficasse so na memoria, reiniciar o bot (atualizacao do Windows,
queda de energia, um Ctrl+C distraido) apagaria tudo em silencio — e a pessoa so
descobriria as 14:30, quando nada acontecesse.

NAO CONFUNDIR COM O CHECKPOINT dos outros fluxos. O checkpoint registra o que JA
FOI FEITO, para poder retomar de onde parou. A agenda registra o que AINDA VAI
SER FEITO. Sao direcoes opostas no tempo.
"""
import json
import threading
import time
from dataclasses import asdict, dataclass, field

from services.paths import DATA_DIR

_PATH = DATA_DIR / "agenda_bot.json"

# O laco de fundo e os comandos do usuario mexem na mesma lista, em threads
# diferentes. Sem o lock, dois "salvar" simultaneos perdem um dos dois.
_LOCK = threading.RLock()

PENDENTE = "pendente"
EXECUTANDO = "executando"
CONCLUIDO = "concluido"
ERRO = "erro"
PERDIDO = "perdido"
CANCELADO = "cancelado"
INDEFINIDO = "indefinido"

# Status que ainda ocupam a agenda (aparecem no /agenda, podem ser cancelados).
ABERTOS = (PENDENTE, EXECUTANDO)


@dataclass
class Item:
    id: str
    chat_id: int
    quem: str            # nome de quem agendou, para o log e o aviso
    chamado: str
    quando_ts: float
    quando_label: str
    status: str = PENDENTE
    detalhe: str = ""


def _ler() -> list:
    if not _PATH.exists():
        return []
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            return [Item(**d) for d in json.load(f)]
    except (json.JSONDecodeError, OSError, TypeError):
        # Arquivo corrompido: melhor comecar vazio do que derrubar o bot na
        # subida. Perde-se a agenda, mas o servico continua de pe.
        return []


def _gravar(itens) -> None:
    """Escrita atomica: grava num temporario e substitui.

    Sem isso, uma queda no meio do write deixa um JSON pela metade — que na
    proxima leitura vira "agenda vazia".

    O temporario termina em ".tmp.json", NAO ".tmp": em desenvolvimento o
    `reflex run` observa a pasta do projeto INTEIRA para hot-reload e ignora
    extensoes conhecidas (json, txt, log...) mas NAO ignora ".tmp" — um arquivo
    terminado em ".tmp" aqui reiniciaria o backend do Reflex a cada agendamento
    gravado, se os dois processos rodarem na mesma maquina. Mesmo bug e mesma
    correcao ja aplicada em `services/checkpoint.py`.
    """
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PATH.parent / (_PATH.name + ".tmp.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump([asdict(i) for i in itens], f, ensure_ascii=False, indent=2)
    tmp.replace(_PATH)


def carregar_ao_subir() -> list:
    """Sanea a agenda na subida do bot. Devolve os itens que ficaram em duvida.

    Item marcado EXECUTANDO quer dizer que o bot caiu no meio de uma execucao:
    nao da para saber se a acao chegou a ser salva no Assyst. Marcar como erro
    seria mentira, marcar como concluido tambem — vira INDEFINIDO, e a pessoa e
    avisada para conferir na mao.
    """
    with _LOCK:
        itens = _ler()
        duvidosos = [i for i in itens if i.status == EXECUTANDO]
        for i in duvidosos:
            i.status = INDEFINIDO
            i.detalhe = "O bot caiu durante a execucao"
        if duvidosos:
            _gravar(itens)
        return duvidosos


def listar(chat_id=None, apenas_abertos=False) -> list:
    with _LOCK:
        itens = _ler()
    if chat_id is not None:
        itens = [i for i in itens if i.chat_id == chat_id]
    if apenas_abertos:
        itens = [i for i in itens if i.status in ABERTOS]
    return sorted(itens, key=lambda i: i.quando_ts)


def adicionar(chat_id, quem, chamado, quando_ts, quando_label) -> Item:
    with _LOCK:
        itens = _ler()
        item = Item(
            id=str(int(time.time() * 1000)),
            chat_id=chat_id,
            quem=quem,
            chamado=chamado,
            quando_ts=quando_ts,
            quando_label=quando_label,
        )
        itens.append(item)
        _gravar(itens)
        return item


def cancelar(item_id, chat_id) -> Item | None:
    """Cancela um item. So o dono cancela — e so enquanto ainda esta PENDENTE."""
    with _LOCK:
        itens = _ler()
        for i in itens:
            if i.id == item_id and i.chat_id == chat_id and i.status == PENDENTE:
                i.status = CANCELADO
                _gravar(itens)
                return i
        return None


def separar_vencidos(agora, tolerancia_s) -> tuple:
    """Devolve (para_rodar, perdidos) e ja marca os dois no arquivo.

    Perdido e agendamento cujo horario passou ha mais que a tolerancia — o
    chamado precisa iniciar NA hora marcada, entao rodar atrasado seria pior do
    que nao rodar. A tolerancia existe so por causa do intervalo do laco.
    """
    with _LOCK:
        itens = _ler()
        rodar, perdidos = [], []
        for i in itens:
            if i.status != PENDENTE or i.quando_ts > agora:
                continue
            if agora - i.quando_ts <= tolerancia_s:
                i.status = EXECUTANDO
                rodar.append(i)
            else:
                i.status = PERDIDO
                i.detalhe = "O bot nao estava no ar na hora marcada"
                perdidos.append(i)
        if rodar or perdidos:
            _gravar(itens)
        return rodar, perdidos


def concluir(item_id, ok, detalhe="") -> None:
    with _LOCK:
        itens = _ler()
        for i in itens:
            if i.id == item_id:
                i.status = CONCLUIDO if ok else ERRO
                i.detalhe = detalhe
                break
        _gravar(itens)
