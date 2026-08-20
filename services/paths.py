"""
services/paths.py — Onde ficam os dados do usuario.

UMA pasta so, na raiz do projeto: `data/`. Antes eram duas — `data/` (checkpoints
e TXT de filhos) e `services/data/` (credenciais e bases de conhecimento) — o que
so complicava: dados do usuario espalhados em dois lugares.

Isso importa na hora de ATUALIZAR o app (ver `atualizar.py`, na raiz): a copia
da atualizacao e ADITIVA (robocopy sem /MIR, nunca apaga nada no destino), entao
nenhum arquivo daqui precisa ser excluido na troca — o que esta so no zip do
GitHub (kb_configs.json, por exemplo, que E versionado) e atualizado; o que so
existe localmente (credenciais.json, checkpoints/, usuarios_bot.json — todos no
.gitignore) simplesmente nao esta no zip, entao sobrevive sem regra nenhuma.

Conteudo de `data/`:
  - checkpoints/       -> progresso linha a linha (Desmembramento e Requisição de Serviço)
  - filhos_*.txt       -> numeros dos chamados filhos criados
  - credenciais.json   -> matricula (a SENHA vai para o Cofre do Windows)
  - kb_configs.json    -> Bases de Conhecimento cadastradas

O QUE **NAO** PODE FICAR EM `data/`: qualquer coisa que escreva muito arquivo,
com o perfil do Chrome da aba Licencas. Motivo concreto, descoberto na marra: em
desenvolvimento o `reflex run` observa a pasta do projeto INTEIRA para hot-reload
(`reload_paths = [Path.cwd()]`). O Chrome cria ~1500 arquivos ao subir um perfil;
isso dispara o reload, o backend reinicia e MATA a thread do worker no meio do
fluxo — a janela abria e nunca era logada. Essas coisas vao para
`APP_LOCAL_DIR`, fora da arvore observada.
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"

# Dados pesados e por-maquina, FORA do projeto: perfil de navegador e afins.
# Fica em %LOCALAPPDATA% (com fallback para a home), que e o lugar padrao do
# Windows para isso — e, de quebra, sobrevive as atualizacoes do app sem precisar
# de regra nenhuma no updater.
APP_LOCAL_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Automatic"
PERFIL_NAVEGADOR_DIR = APP_LOCAL_DIR / "perfil_navegador"

# Perfil persistente do Edge usado só pela automação de Ponto (Senior HCM) — site e
# credencial totalmente à parte do Assyst, por isso pasta própria (mesmo motivo do
# PERFIL_NAVEGADOR_DIR acima: fora da árvore do projeto, longe do hot-reload).
PERFIL_PONTO_DIR = APP_LOCAL_DIR / "perfil_ponto"

# Onde uma atualização baixada pelo app (state/update_state.py) fica esperando até
# ser aplicada — também fora da árvore do projeto, pelo mesmo motivo dos perfis
# acima: escrever centenas de arquivos dentro do projeto, com o 'reflex run' de
# olho na pasta inteira, dispararia o hot-reload no meio do download. Quem
# efetivamente troca os arquivos do projeto é `atualizar.py` (raiz), sempre com o
# app fechado — ver o docstring de lá.
UPDATE_STAGING_DIR = APP_LOCAL_DIR / "update_pendente"
