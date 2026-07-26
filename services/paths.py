"""
services/paths.py — Onde ficam os dados do usuario.

UMA pasta so, na raiz do projeto: `data/`. Antes eram duas — `data/` (checkpoints
e TXT de filhos) e `services/data/` (credenciais e bases de conhecimento) — o que
so complicava: dados do usuario espalhados em dois lugares.

Isso importa na hora de ATUALIZAR o app: a pasta de dados e justamente o que o
updater precisa EXCLUIR ao copiar a versao nova, senao a atualizacao apaga os
checkpoints, as BCs cadastradas e a matricula. Uma pasta = uma regra de exclusao.

Conteudo de `data/`:
  - checkpoints/       -> progresso linha a linha do Desmembramento
  - filhos_*.txt       -> numeros dos chamados filhos criados
  - credenciais.json   -> matricula (a SENHA vai para o Cofre do Windows)
  - kb_configs.json    -> Bases de Conhecimento cadastradas
"""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
CHECKPOINTS_DIR = DATA_DIR / "checkpoints"
