"""
services/paths.py — Onde ficam os dados do usuario.

UMA pasta so, na raiz do projeto: `data/`. Antes eram duas — `data/` (checkpoints
e TXT de filhos) e `services/data/` (credenciais e bases de conhecimento) — o que
so complicava: dados do usuario espalhados em dois lugares.

Isso importa na hora de ATUALIZAR o app: a pasta de dados e justamente o que o
updater precisa EXCLUIR ao copiar a versao nova, senao a atualizacao apaga os
checkpoints, as BCs cadastradas e a matricula. Uma pasta = uma regra de exclusao.

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

DATA_DIR = Path(__file__).parent.parent / "data"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"

# Dados pesados e por-maquina, FORA do projeto: perfil de navegador e afins.
# Fica em %LOCALAPPDATA% (com fallback para a home), que e o lugar padrao do
# Windows para isso — e, de quebra, sobrevive as atualizacoes do app sem precisar
# de regra nenhuma no updater.
APP_LOCAL_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Automatic"
PERFIL_NAVEGADOR_DIR = APP_LOCAL_DIR / "perfil_navegador"
