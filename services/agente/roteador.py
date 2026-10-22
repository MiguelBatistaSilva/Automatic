"""
services/agente/roteador.py — De que DOMÍNIO é o pedido? (07/10)

Para o agente crescer (mais fluxos, documentos...) sem que cada ida à IA
carregue TODAS as ferramentas e TODA a base: só vão as do domínio do pedido.
Antes disto iam 18 ferramentas + a base inteira em toda ida (~3.700 tokens),
e a Groq grátis limita tokens por minuto.

Sem IA de propósito: uma ida a mais só para classificar custaria o tempo que
o corte de 02/10 economizou (ver ferramentas._com_ultima_acao). São palavras
por domínio, procuradas em TODAS as mensagens do técnico na conversa — a
resposta "sim"/"o primeiro" não tem palavra-chave, mas a conversa tem.

A REGRA DE SEGURANÇA: na dúvida, manda tudo. Nenhum domínio reconhecido =
`None` = todas as ferramentas e a base inteira, exatamente como antes. O
roteador só pode economizar; nunca deixa o modelo sem a ferramenta certa
por não ter entendido o pedido. Casar demais (dois domínios) também é
seguro — só gasta um pouco mais.

Domínio novo: uma entrada aqui + a subpasta em conhecimento/ + `dominio=`
nas ferramentas dele (os três com o MESMO nome).
"""

import re

# domínio -> padrão (sem acento e minúsculo; ver _normalizar)
DOMINIOS: dict[str, re.Pattern] = {
    "chamados": re.compile(
        r"\b[rs]\d{6,}\b|chamad|resolv|desmembr|\bbases?\b|\bsla\b|atendiment"
        r"|fornecedor|aguard|retom|pausa|informac|program|procediment"
        r"|minha fila|\bfila do\b|estourad|prazo"
        # Despacho ao Serviço de Operações (20/10): despachar_operacao.
        r"|despach|condena|\boperac"
        # Atribuição Interna (21/10): atribuir_chamado.
        r"|atribu|encaminh|escalon|\bpux|\bpega"
        # Triagem (22/10): analisar_chamado.
        r"|analis|triag|item b\b"),
    # Plantão Judiciário do fim de semana (13/10): criar_plantoes.
    "requisicao": re.compile(r"requisic|tombo|patrimon|matricula|plant(ao|oes)"),
    # Verbo antes OU depois de "fila" ("configura a fila X" / "a fila X
    # configurada"), ou a fila indo para o Assyst/menu. Frases achadas pelo
    # eval_roteador.py em 08/10.
    "filas": re.compile(
        r"(configur|cri[ae]|adicion|mont|cadastr|coloc)\w*\b.{0,40}\bfilas?\b"
        r"|\bfilas?\b.{0,60}\b(configurad|criad|adicionad|cadastrad)"
        r"|\bfilas?\b.{0,40}\bno (meu )?(assyst|menu)\b|perfil de coluna"),
    # Termo de Responsabilidade de Instalação e Termo de Tarefa de Demanda (10/10).
    "termos": re.compile(
        r"\btermos?\b|\bbackup\b|troca de (maquina|micro|computador|equipamento|pc)"
        r"|\bdemanda\b|\bevento\b|validador|comprovacao de prestacao"),
}


# Conversa solta (21/10): "bom dia", "valeu", "conta uma piada". Só quando
# NADA na conversa casou com um domínio — aí vai só a personalidade, sem
# ferramentas nem base (~5x menos tokens que mandar tudo). Se for um pedido
# disfarçado, a IA diz "ainda não sei fazer" e a rede de segurança do
# assistente refaz com tudo.
CONVERSA = "conversa"
_PAPO = re.compile(
    r"\b(oi+|ola|opa|e ?ai|eae|fala|bom dia|boa tarde|boa noite|valeu|vlw"
    r"|obrigad\w*|brigad\w*|tmj|tamo junto|show|top|massa|arretado|beleza|blz"
    r"|parabens|tudo (bem|bom|certo|joia)|k{2,}|(ha){2,}|rs+)\b")
_PAPO_SEMPRE = re.compile(
    r"piada|quem (e|eh) voce|voce (e|eh) (humano|gente|robo|uma ia|real)"
    r"|seu nome|como (vai|voce (esta|ta))")


def _normalizar(texto: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def dominios(historico: list[dict]) -> "set[str] | None":
    """Domínios citados pelo técnico na conversa; None = não sei (manda tudo)."""
    texto = _normalizar(" ".join(h.get("content") or "" for h in historico
                                 if h.get("role") == "user"))
    achados = {nome for nome, padrao in DOMINIOS.items() if padrao.search(texto)}
    # No termo, tombo/matrícula são dados da máquina e do usuário, não um
    # pedido de requisição: só puxa requisição se a palavra aparecer (10/10).
    # Idem no despacho à Operação: o tombo é do equipamento (20/10).
    despacho = re.search(r"despach|condena|\boperac", texto)
    if ("termos" in achados or despacho) and not re.search(r"requisic", texto):
        achados.discard("requisicao")
    if not achados:
        ultima = _normalizar(next((h.get("content") or "" for h in reversed(historico)
                                   if h.get("role") == "user"), ""))
        if _PAPO_SEMPRE.search(ultima) or (_PAPO.search(ultima) and len(ultima.split()) <= 6):
            return {CONVERSA}
    return achados or None
