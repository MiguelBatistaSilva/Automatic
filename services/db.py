"""
services/db.py — O banco SQLite do Automatic (um arquivo so, por maquina).

POR QUE SQLITE (2026-09-28): os dados viviam em JSONs gravados com `open("w")`
direto — que ZERA o arquivo antes de escrever (morrer nesse instante corrompe) —
e o bot e a UI do Reflex sao PROCESSOS separados mexendo nos mesmos arquivos (o
RLock da agenda so protege dentro de um processo). No SQLite cada gravacao e uma
transacao: entra inteira ou nao entra, e em modo WAL varios processos convivem.
E stdlib — nenhum pacote novo no pacotes_automacao.

ONDE FICA: em APP_LOCAL_DIR (%LOCALAPPDATA%\\Automatic), NAO em data/. O WAL
escreve automatic.db, -wal e -shm a cada gravacao; dentro do projeto isso
dispararia o hot-reload do `reflex run` no meio de um fluxo (mesmo bug do .tmp
do checkpoint, 2026-08-11). De quebra, sobrevive as atualizacoes sem regra.

MIGRACAO DOS JSONs: na primeira conexao de cada processo, cada JSON antigo
ainda nao importado e lido, inserido no banco e renomeado para
`*.json.migrado` (backup — nada e apagado). A tabela `migracoes_json` registra
o que ja foi importado: se o updater (copia aditiva) trouxer o JSON de volta
do zip, ele e ignorado em vez de sobrescrever o que ja esta no banco.

ESQUEMA VERSIONADO: `PRAGMA user_version` + lista `_ESQUEMA`. Para evoluir o
banco, ACRESCENTE um item no fim da lista — nunca edite um que ja rodou.
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from services.paths import APP_LOCAL_DIR, CHECKPOINTS_DIR, DATA_DIR

DB_PATH = APP_LOCAL_DIR / "automatic.db"

# Cada item leva o banco da versao N para N+1.
_ESQUEMA: list[str] = [
    # v1 — 2026-09-28: usuarios do bot, credenciais do bot, presets da Requisicao.
    """
    CREATE TABLE migracoes_json (
        nome        TEXT PRIMARY KEY,
        migrado_em  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    );

    -- Whitelist do bot (bot/usuarios.py): quem pode falar com ele.
    CREATE TABLE bot_usuarios (
        chat_id  TEXT PRIMARY KEY,
        nome     TEXT NOT NULL
    );

    -- Matricula de cada pessoa no Assyst (bot/services/credencial_servico.py).
    -- A SENHA nao fica aqui: continua no Cofre do Windows (keyring).
    CREATE TABLE bot_credenciais (
        chat_id    TEXT PRIMARY KEY,
        matricula  TEXT NOT NULL
    );

    -- Presets da Requisicao (services/requisicao_presets.py). `ordem` preserva
    -- a ordem em que os valores foram cadastrados (e a dos botoes no bot).
    CREATE TABLE requisicao_presets (
        campo  TEXT NOT NULL,
        valor  TEXT NOT NULL,
        ordem  INTEGER NOT NULL,
        PRIMARY KEY (campo, valor)
    );
    """,
    # v2 — 2026-09-28: Bases de Conhecimento. Cada tecnico cadastra as proprias;
    # o kb_configs.json versionado era SOBRESCRITO pelo updater a cada
    # atualizacao (robocopy copia por cima), apagando os cadastros locais.
    # `id` preserva a ordem de cadastro.
    """
    CREATE TABLE kb_bases (
        id           INTEGER PRIMARY KEY,
        keyword      TEXT NOT NULL,
        nome_artigo  TEXT NOT NULL
    );
    """,
    # v3 — 2026-09-28: tarefas. Nasce com a agenda do Iniciar Atendimento
    # (bot/agenda.py, tipo 'atendimento'), mas ja no formato da futura fila de
    # tarefas de todos os fluxos: `tipo` diz qual fluxo, `dados` (JSON) leva os
    # parametros dele, `executar_em` NULL significara "assim que possivel".
    """
    CREATE TABLE tarefas (
        id                 TEXT PRIMARY KEY,
        tipo               TEXT NOT NULL,
        chat_id            INTEGER,
        quem               TEXT NOT NULL DEFAULT '',
        dados              TEXT NOT NULL DEFAULT '{}',
        executar_em        REAL,
        executar_em_label  TEXT NOT NULL DEFAULT '',
        status             TEXT NOT NULL,
        detalhe            TEXT NOT NULL DEFAULT '',
        criado_em          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
        atualizado_em      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
    );
    CREATE INDEX tarefas_status ON tarefas (status, executar_em);
    """,
    # v4 — 2026-09-28: checkpoints (services/checkpoint.py) e config do app.
    # `extra` (JSON) guarda os campos livres de cada linha (salvo_em,
    # concluido_em, numero=/usuario= da Requisicao...). `numero_filho` e coluna
    # propria para poder consultar "quais filhos esse pai gerou" e vice-versa.
    """
    CREATE TABLE checkpoints (
        chave          TEXT PRIMARY KEY,
        total          INTEGER NOT NULL,
        criado_em      TEXT NOT NULL,
        atualizado_em  TEXT NOT NULL,
        concluido      INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE checkpoint_linhas (
        chave         TEXT NOT NULL REFERENCES checkpoints (chave) ON DELETE CASCADE,
        idx           INTEGER NOT NULL,
        status        TEXT NOT NULL,
        numero_filho  TEXT NOT NULL DEFAULT '',
        extra         TEXT NOT NULL DEFAULT '{}',
        PRIMARY KEY (chave, idx)
    );
    CREATE INDEX checkpoint_linhas_filho ON checkpoint_linhas (numero_filho);

    -- Configuracoes soltas do app (ex.: 'matricula' de quem usa a UI).
    CREATE TABLE app_config (
        chave  TEXT PRIMARY KEY,
        valor  TEXT NOT NULL
    );
    """,
]

_init_lock = threading.Lock()
_inicializado = False


def _abrir() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None: transacoes explicitas (BEGIN/COMMIT) em transacao().
    # timeout: espera ate 10 s se o outro processo estiver gravando.
    con = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


@contextmanager
def transacao():
    """Conexao dentro de UMA transacao: commit no fim, rollback se der erro.

    BEGIN IMMEDIATE reserva a escrita ja na entrada — dois processos fazendo
    ler-e-regravar ao mesmo tempo esperam um pelo outro em vez de um perder
    a gravacao do outro.
    """
    _garantir_inicializado()
    con = _abrir()
    try:
        con.execute("BEGIN IMMEDIATE")
        try:
            yield con
        except BaseException:
            con.execute("ROLLBACK")
            raise
        con.execute("COMMIT")
    finally:
        con.close()


@contextmanager
def leitura():
    """Conexao para VARIAS consultas que precisam ver o mesmo instante do
    banco (ex.: cabecalho + linhas de um checkpoint), sem travar a escrita."""
    _garantir_inicializado()
    con = _abrir()
    try:
        con.execute("BEGIN")
        try:
            yield con
        finally:
            con.execute("ROLLBACK")
    finally:
        con.close()


def consultar(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Leitura simples, fora de transacao de escrita."""
    _garantir_inicializado()
    con = _abrir()
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


# --------------------------------------------------------------------------- #
# Inicializacao: esquema + importacao dos JSONs antigos
# --------------------------------------------------------------------------- #

def _garantir_inicializado() -> None:
    global _inicializado
    if _inicializado:
        return
    with _init_lock:
        if _inicializado:
            return
        con = _abrir()
        try:
            # IMMEDIATE: se bot e UI subirem juntos, so um aplica o esquema e
            # importa os JSONs; o outro espera e depois ve tudo pronto.
            con.execute("BEGIN IMMEDIATE")
            try:
                _aplicar_esquema(con)
                renomear = _importar_jsons(con) + _importar_checkpoints(con)
            except BaseException:
                con.execute("ROLLBACK")
                raise
            con.execute("COMMIT")
        finally:
            con.close()
        # So renomeia DEPOIS do commit: se algo falhar antes, o JSON continua
        # no lugar e a importacao e refeita na proxima subida.
        for p in renomear:
            try:
                p.replace(p.with_name(p.name + ".migrado"))
            except OSError:
                pass  # ja registrado em migracoes_json; nao sera relido
        _inicializado = True


def _aplicar_esquema(con: sqlite3.Connection) -> None:
    versao = con.execute("PRAGMA user_version").fetchone()[0]
    for i, script in enumerate(_ESQUEMA[versao:], start=versao + 1):
        for comando in script.split(";"):
            if comando.strip():
                con.execute(comando)
        con.execute(f"PRAGMA user_version = {i}")


def _ler_json(p: Path):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _importar_jsons(con: sqlite3.Connection) -> list[Path]:
    """Importa cada JSON ainda nao migrado. Devolve os arquivos a renomear."""
    importadores = {
        "usuarios_bot.json": _imp_usuarios,
        "credencial_bot.json": _imp_credenciais,
        "requisicao_presets.json": _imp_presets,
        "kb_configs.json": _imp_kb,
        "agenda_bot.json": _imp_agenda,
        "credenciais.json": _imp_credenciais_app,
    }
    renomear = []
    for nome, importar in importadores.items():
        if con.execute("SELECT 1 FROM migracoes_json WHERE nome = ?",
                       (nome,)).fetchone():
            continue
        p = DATA_DIR / nome
        if p.exists():
            dados = _ler_json(p)
            if dados is None:
                # Ilegivel: NAO marca como migrado nem renomeia — o arquivo
                # fica para alguem olhar, e a proxima subida tenta de novo.
                continue
            importar(con, dados)
            renomear.append(p)
        con.execute("INSERT INTO migracoes_json (nome) VALUES (?)", (nome,))
    return renomear


def _imp_usuarios(con, dados: dict) -> None:
    for chat_id, nome in dados.items():
        con.execute("INSERT OR REPLACE INTO bot_usuarios VALUES (?, ?)",
                    (str(chat_id), nome))


# chat_id do Miguel — dono da credencial unica do formato antigo (ver
# credencial_servico.py). Repetido aqui porque o JSON ainda pode estar nesse
# formato numa maquina que nunca rodou a migracao de 2026-08-26.
_CHAT_ID_CREDENCIAL_ANTIGA = "1070692564"


def _imp_credenciais(con, dados: dict) -> None:
    if "matricula" in dados:
        dados = {_CHAT_ID_CREDENCIAL_ANTIGA: dados["matricula"]}
    for chat_id, matricula in dados.items():
        con.execute("INSERT OR REPLACE INTO bot_credenciais VALUES (?, ?)",
                    (str(chat_id), matricula))


def _imp_presets(con, dados: dict) -> None:
    for campo, valores in dados.items():
        for ordem, valor in enumerate(valores):
            con.execute(
                "INSERT OR IGNORE INTO requisicao_presets VALUES (?, ?, ?)",
                (campo, valor, ordem))


def _imp_kb(con, dados: list) -> None:
    for e in dados:
        con.execute("INSERT INTO kb_bases (keyword, nome_artigo) VALUES (?, ?)",
                    (e["keyword"], e["nome_artigo"]))


def _imp_agenda(con, dados: list) -> None:
    for i in dados:
        con.execute(
            "INSERT OR IGNORE INTO tarefas (id, tipo, chat_id, quem, dados, "
            "executar_em, executar_em_label, status, detalhe) "
            "VALUES (?, 'atendimento', ?, ?, ?, ?, ?, ?, ?)",
            (i["id"], i["chat_id"], i["quem"],
             json.dumps({"chamado": i["chamado"]}, ensure_ascii=False),
             i["quando_ts"], i["quando_label"], i["status"], i.get("detalhe", "")))


def _imp_credenciais_app(con, dados: dict) -> None:
    if dados.get("matricula"):
        con.execute("INSERT OR REPLACE INTO app_config VALUES ('matricula', ?)",
                    (dados["matricula"],))


def _importar_checkpoints(con: sqlite3.Connection) -> list[Path]:
    """Importa os checkpoints JSON que ainda estiverem em data/checkpoints/.

    Diferente dos outros JSONs, roda a CADA subida (nao usa migracoes_json):
    sao muitos arquivos, e o que ja foi importado virou .migrado e nao casa
    mais com o glob. Checkpoint ILEGIVEL nao e importado nem renomeado — fica
    no lugar, e `checkpoint.esta_corrompido` continua barrando o fluxo, como
    antes (importar como "nao existe" faria o fluxo RECRIAR os filhos).
    """
    if not CHECKPOINTS_DIR.exists():
        return []
    arquivos = [p for p in CHECKPOINTS_DIR.glob("*/*.json")
                if not p.name.endswith(".tmp.json")]
    # Formato de antes de 17/09: JSON solto direto em checkpoints/.
    arquivos += [p for p in CHECKPOINTS_DIR.glob("*.json")
                 if not p.name.endswith(".tmp.json")]
    renomear = []
    for p in arquivos:
        dados = _ler_json(p)
        if not isinstance(dados, dict) or "linhas" not in dados:
            continue
        chave = dados.get("numero_chamado") or p.stem
        if con.execute("SELECT 1 FROM checkpoints WHERE chave = ?",
                       (chave,)).fetchone():
            continue  # o banco ja manda nesta chave; o arquivo fica como esta
        linhas = dados.get("linhas", [])
        con.execute(
            "INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?)",
            (chave, dados.get("total", len(linhas)), dados.get("criado_em", ""),
             dados.get("atualizado_em", ""), int(bool(dados.get("concluido")))))
        for l in linhas:
            extra = {k: v for k, v in l.items()
                     if k not in ("index", "status", "numero_filho")}
            con.execute(
                "INSERT INTO checkpoint_linhas VALUES (?, ?, ?, ?, ?)",
                (chave, l["index"], l["status"], l.get("numero_filho", ""),
                 json.dumps(extra, ensure_ascii=False)))
        renomear.append(p)
    return renomear
