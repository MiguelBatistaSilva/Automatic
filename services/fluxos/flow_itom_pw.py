"""
services/fluxos/flow_itom_pw.py — Dados da máquina pelo TOMBO no Itom (assyst
ITAM), só leitura (30/10).

Não há banco geral de tombos e seriais: o Itom (agente instalado nas máquinas)
tem a ficha de cada uma, e o sistema busca NA HORA quando precisa — o Termo de
Responsabilidade e o despacho à Operação pedem o nº de série. Extrair tudo de
uma vez levaria horas (o serial só aparece na página de cada máquina).

Receita validada em 30/10 (tombos 333209 e 332154):
  - Login em LoginPage.do com `tjce-dom-01\\<matrícula>` e a senha do Assyst.
  - Discovery (`sub_menu_disc`) -> `#search` + `#goBtn` (busca por "contém").
  - Na grade, o Host Name (`.x-grid-cell-dis-name span[onclick]`) termina com
    o tombo (FCB13FAMI333209); o onclick leva a InventoryDetails.jsp.
  - A ficha é uma grade de pares parâmetro/valor: 'System Serial No', IP,
    sistema operacional, processador, RAM... Marca e modelo NÃO aparecem.
  ~6 s de login e ~4,5 s por tombo. O Itom é outro sistema: abre o próprio
Chrome, separado da sessão do Assyst.
"""

import dataclasses

from services.assyst.browser_pw import NavegadorPW

BASE = "http://10.1.1.86"
_URL_LOGIN = BASE + "/assystITAM/LoginPage.do"
_SEL_DISCOVERY = "a[href='reDirectionPage.do?subModule=sub_menu_disc']"
_DOMINIO = "tjce-dom-01"

_JS_HOSTS = r"""() => [...document.querySelectorAll(".x-grid-cell-dis-name span[onclick]")].map(s => ({
    host: s.innerText.trim(), ip: s.title || "",
    url: (s.getAttribute('onclick').match(/href="?([^"]+)"?/) || [])[1] || ""}))"""
_JS_PARES = r"""() => [...document.querySelectorAll('tr.x-grid-row')].map(r =>
    [...r.querySelectorAll('.x-grid-cell-inner')].map(c => c.innerText.trim()))
    .filter(c => c.length === 2 && c[0])"""

# Os tombos já consultados nesta execução do app: serial não muda.
_cache: dict[str, "Maquina"] = {}


@dataclasses.dataclass
class Maquina:
    tombo: str
    hostname: str = ""
    serial: str = ""
    ip: str = ""
    sistema: str = ""
    processador: str = ""
    ram: str = ""
    sem_comunicar: str = ""      # 'Down Since' do Itom
    outras: list[str] = dataclasses.field(default_factory=list)  # outros hosts achados

    def resumo(self) -> str:
        partes = [f"hostname {self.hostname}", f"série {self.serial or '?'}"]
        partes += [x for x in (self.sistema, self.processador) if x]
        if self.ram:
            partes.append(f"RAM {self.ram} MB")
        if self.sem_comunicar:
            partes.append(f"sem comunicar com o Itom há {self.sem_comunicar}")
        return f"Tombo {self.tombo}: " + "; ".join(partes)


def _login(page, matricula: str, senha: str, log) -> bool:
    log("Entrando no Itom...", "status")
    page.goto(_URL_LOGIN, timeout=30000)
    page.fill("#userName", f"{_DOMINIO}\\{matricula}")
    page.fill("#password", senha)
    page.click("#loginId")
    page.wait_for_load_state("networkidle", timeout=30000)
    if page.locator(_SEL_DISCOVERY).count() == 0:
        log("O Itom recusou o login (confira a senha em Credenciais).", "error")
        return False
    page.click(_SEL_DISCOVERY)
    page.wait_for_load_state("networkidle", timeout=30000)
    return True


def _hosts(page, tombo: str) -> list[dict]:
    page.fill("#search", tombo)
    page.click("#goBtn")
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(1000)
    achados = [h for h in page.evaluate(_JS_HOSTS) if tombo in h["host"]]
    # O tombo fica no FIM do nome; "contém" pegaria 1333209 para 333209.
    fim = [h for h in achados if h["host"].upper().endswith(tombo)]
    return fim or achados


def _ficha(page, tombo: str, h: dict) -> Maquina:
    page.goto(f"{BASE}/ITOM/{h['url']}", timeout=30000)
    page.wait_for_load_state("networkidle", timeout=30000)
    page.wait_for_timeout(800)
    p = dict(page.evaluate(_JS_PARES))
    return Maquina(tombo=tombo, hostname=p.get("Host Name") or h["host"],
                   serial=p.get("System Serial No", ""), ip=p.get("IP Address", h["ip"]),
                   sistema=p.get("OS", ""), processador=p.get("Processor Name", ""),
                   ram=(p.get("RAM Size (MB)", "").split("[")[0]),
                   sem_comunicar=p.get("Down Since", ""))


def consultar(tombos: list[str], matricula: str, senha: str, log) -> dict[str, "Maquina | None"]:
    """{tombo: Maquina ou None (não está no Itom)}. Levanta RuntimeError se
    não der para entrar no Itom."""
    tombos = [t.strip() for t in tombos if t and t.strip()]
    saida = {t: _cache[t] for t in tombos if t in _cache}
    faltam = [t for t in tombos if t not in saida]
    if not faltam:
        return saida
    with NavegadorPW(log) as page:
        if not _login(page, matricula, senha, log):
            raise RuntimeError("o Itom recusou o login")
        for tombo in faltam:
            log(f"Buscando o tombo {tombo} no Itom...", "status")
            hosts = _hosts(page, tombo)
            if not hosts:
                saida[tombo] = None
                continue
            m = _ficha(page, tombo, hosts[0])
            m.outras = [h["host"] for h in hosts[1:]]
            _cache[tombo] = saida[tombo] = m
            page.go_back()
            page.wait_for_load_state("networkidle", timeout=30000)
    return saida
