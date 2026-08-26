"""
state/update_state.py — Back-end do pop-up "Atualização" (ícone no topo da sidebar).

Três passos, cada um mais "perigoso" que o anterior:
  1. verificar()  — só lê o manifesto remoto. Sempre seguro.
  2. baixar()     — baixa e extrai pra fora do projeto (UPDATE_STAGING_DIR).
                    Ainda seguro com o app aberto — não toca em nada daqui.
  3. aplicar_e_reiniciar() — este SIM fecha o app. Dispara `atualizar.py` (raiz)
     como processo destacado e não tenta se encerrar graciosamente: quem mata o
     processo (árvore inteira, frontend incluso) é o `atualizar.py`, via
     taskkill. Depois disso ele troca os arquivos e sobe o
     `iniciar_automatic.bat` de novo sozinho — ver o docstring de lá para o
     porquê de precisar fechar (o 'reflex run' observa o projeto inteiro e
     reinicia sozinho a cada arquivo alterado; aplicar ao vivo derrubaria o
     backend no meio da troca).
"""
import asyncio
import os
import subprocess
import sys

import reflex as rx

from version import VERSION


class UpdateState(rx.State):
    aberto: bool = False
    verificando: bool = False
    baixando: bool = False

    status: str = ""
    status_cor: str = "#6B7280"

    disponivel: bool = False
    versao_disponivel: str = ""
    url_download: str = ""
    pronto_para_reiniciar: bool = False

    @rx.event
    def abrir(self):
        self.status = ""
        self.status_cor = "#6B7280"
        self.aberto = True

    @rx.event
    def set_aberto(self, v: bool):
        self.aberto = v

    @rx.event(background=True)
    async def verificar(self):
        async with self:
            if self.verificando:
                return
            self.verificando = True
            self.status = "Verificando..."
            self.status_cor = "#6B7280"
        yield

        from services.update_service import verificar as verificar_remoto
        res = await asyncio.to_thread(verificar_remoto, VERSION)

        async with self:
            self.verificando = False
            if res:
                remota, url = res
                self.disponivel = True
                self.versao_disponivel = remota
                self.url_download = url
                self.status = f"Nova versão disponível: v{remota}"
                self.status_cor = "#16A34A"
            else:
                self.disponivel = False
                self.status = "Você está na versão mais recente."
                self.status_cor = "#6B7280"

    @rx.event(background=True)
    async def baixar(self):
        async with self:
            if self.baixando or not self.url_download:
                return
            self.baixando = True
            self.status = "Baixando..."
        yield

        from services.update_service import baixar_e_preparar

        def log(msg, tipo="info"):
            pass  # sem console de log aqui — só o status importa pro usuário

        ok = await asyncio.to_thread(
            baixar_e_preparar, self.url_download, self.versao_disponivel, log
        )

        async with self:
            self.baixando = False
            if ok:
                self.pronto_para_reiniciar = True
                self.status = "Baixado! Clique em \"Reiniciar e aplicar\"."
                self.status_cor = "#16A34A"
            else:
                self.status = "Falha ao baixar. Tente de novo mais tarde."
                self.status_cor = "#DC2626"

    @rx.event
    def aplicar_e_reiniciar(self):
        from services.paths import PROJECT_ROOT

        self.status = "Reiniciando... aguarde uns 15s e recarregue a página."
        self.status_cor = "#0891B2"

        pid_atual = os.getpid()
        # "cmd /c start" (não Popen direto) de propósito: atualizar.py precisa
        # sobreviver ao `taskkill /T` que ELE MESMO dispara em cima de
        # pid_atual. Um Popen direto registra atualizar.py como filho de
        # pid_atual, e /T mata a árvore inteira — incluindo o próprio
        # atualizar.py antes de ele conseguir reabrir o app (comprovado com
        # reprodução isolada: o processo morre logo após o taskkill, nunca
        # loga além disso). O "start" cria um cmd.exe intermediário que
        # encerra na hora, então quando o taskkill roda, esse elo já sumiu do
        # retrato de processos vivos e não dá pra descer até atualizar.py.
        subprocess.Popen(
            ["cmd", "/c", "start", "", sys.executable,
             str(PROJECT_ROOT / "atualizar.py"), "--reiniciar", str(pid_atual)],
            cwd=str(PROJECT_ROOT),
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        # Não tenta se encerrar graciosamente daqui: quem mata a árvore de
        # processos inteira (incluindo o frontend que o 'reflex run' sobe como
        # filho) é o `atualizar.py`, via taskkill /T. Sair só do processo atual
        # deixaria o frontend órfão, preso na porta.
