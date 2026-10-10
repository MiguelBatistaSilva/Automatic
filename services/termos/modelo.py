"""
services/termos/modelo.py — Os DADOS de um Termo de Responsabilidade (10/10).

Um modelo só para os três termos que existiam em planilha:
  - 1 troca  -> layout individual (usuário recebedor no topo);
  - N trocas -> um bloco por máquina e as declarações depois, em letra menor;
  - nos dois, UMA assinatura no fim (quem acompanhou o serviço);
  - `backup` muda só o texto da declaração (com / sem backup e restore).
Campo vazio sai em branco no documento, para preencher à mão.
"""

import dataclasses
import datetime


@dataclasses.dataclass
class Equipamento:
    marca_modelo: str = ""
    tombo: str = ""
    serie: str = ""
    hostname: str = ""


@dataclasses.dataclass
class Pessoa:
    nome: str = ""
    matricula: str = ""


@dataclasses.dataclass
class Troca:
    desinstalada: Equipamento = dataclasses.field(default_factory=Equipamento)
    instalada: Equipamento = dataclasses.field(default_factory=Equipamento)


@dataclasses.dataclass
class Termo:
    backup: bool                      # True = COM backup e restore
    unidade: str = ""
    chamado: str = ""
    data: "datetime.date | None" = None
    trocas: list[Troca] = dataclasses.field(default_factory=lambda: [Troca()])
    # Quem recebeu/acompanhou o serviço — assina o termo (uma vez só).
    recebedor: Pessoa = dataclasses.field(default_factory=Pessoa)
    trava: bool = True                # declaração da trava de segurança
    onedrive: "bool | None" = None    # só no COM backup; None = não marcado
    observacoes: str = ""

    @property
    def varias(self) -> bool:
        return len(self.trocas) > 1

    @property
    def titulo(self) -> str:
        return "Termo de Responsabilidade de Instalação"

    @property
    def subtitulo(self) -> str:
        return "Com backup e restore" if self.backup else "Sem backup e restore"
