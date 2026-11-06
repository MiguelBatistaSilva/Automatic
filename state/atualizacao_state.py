"""
state/atualizacao_state.py — O aviso de versão nova na barra do topo.

É só aviso: atualizar continua sendo pelo atualizar_automatic.bat, com o app fechado
(ver atualizar.py). Em background porque a consulta ao GitHub pode demorar, e não
pode segurar a tela.
"""

import asyncio

import reflex as rx


class AtualizacaoState(rx.State):
    versao_nova: str = ""

    @rx.event(background=True)
    async def verificar(self):
        from services.update_service import versao_nova
        from version import VERSION
        nova = await asyncio.to_thread(versao_nova, VERSION)
        async with self:
            self.versao_nova = nova
