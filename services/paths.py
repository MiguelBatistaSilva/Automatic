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
  - checkpoints/<ref>/ -> uma subpasta por chamado (ou hash, na Requisição de
                          Serviço), com o JSON de progresso linha a linha E o
                          TXT dos filhos criados (Desmembramento) juntos
  - credenciais.json   -> matricula (a SENHA vai para o Cofre do Windows)
  - *.json.migrado     -> backups dos JSONs ja importados para o SQLite
                          (o banco fica em APP_LOCAL_DIR — ver services/db.py)

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

# Onde a atualização baixada (atualizar_automatic.bat -> atualizar.py --baixar)
# fica extraída até ser copiada por cima do projeto — fora da árvore do projeto,
# para nunca deixar um download pela metade misturado aos arquivos do app.
UPDATE_STAGING_DIR = APP_LOCAL_DIR / "update_pendente"
