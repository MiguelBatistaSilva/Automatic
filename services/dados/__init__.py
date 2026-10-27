"""
services/dados — O que lê e grava dado LOCAL (sem navegador).

  db.py                  o banco SQLite (um arquivo só, por máquina)
  checkpoint.py          progresso linha a linha dos fluxos (no banco)
  credenciais.py         matrícula (banco) + senha (Cofre do Windows)
  kb_store.py            Bases de Conhecimento cadastradas (no banco)
  requisicao_presets.py  valores pré-cadastrados do /requisicao (no banco)
  referencia.py          CSVs de data/referencia/ (filas, técnicos, edifícios)

Onde ficam as pastas de dados: services/paths.py.
"""
