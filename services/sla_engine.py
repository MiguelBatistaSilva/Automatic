from datetime import datetime

TIPOS_PAUSA = {
    'Aguardando Info do Usuário *',
    'Aguardando Info do Fornecedor',
    'Aguardando Info do Gestor',
    'Atendimento Programado',
}
TIPOS_RETOMADA = {
    'Atendimento Iniciado',
    'Info Recebida do Fornecedor',
    'Info Recebidas do Gestor',
    'Info Recebidas do Usuário *',
}
LIMITE_HORAS = 3
LIMITE_SEGUNDOS = LIMITE_HORAS * 3600


def _parse_data(data_str: str):
    data_str = data_str.replace('\xa0', ' ').strip()
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%Y-%m-%d %H:%M:%S", "%m/%d/%y %I:%M %p"):
        try:
            return datetime.strptime(data_str, fmt)
        except ValueError:
            continue
    return None


def _formatar_segundos(segundos: float) -> str:
    abs_s = abs(int(segundos))
    return f"{abs_s // 3600:02d}h {(abs_s % 3600) // 60:02d}min"


def calcular_sla(historico: list) -> dict:
    """
    Calcula o tempo líquido de SLA a partir do histórico de ações do chamado.
    O relógio é pausado nos tipos de espera e retomado nos tipos de retomada.
    Retorna um dict com: inicio, tempo_gasto_str, tempo_restante_str, estourado, mensagem.
    """
    if not historico:
        return {"estourado": False, "mensagem": "Sem historico para calcular."}

    acoes = list(reversed(historico))
    tempo_total = 0.0
    relogio_correndo = True
    ultimo_marcador = None
    primeira_data = None

    for acao in acoes:
        data_acao = _parse_data(acao.get('data', ''))
        if not data_acao:
            continue

        tipo = acao.get('tipo', '').strip()

        if primeira_data is None:
            primeira_data = data_acao
            ultimo_marcador = data_acao
            # Avalia o tipo já na primeira ação para iniciar pausado se necessário
            if tipo in TIPOS_PAUSA:
                relogio_correndo = False
            continue

        if relogio_correndo:
            delta = (data_acao - ultimo_marcador).total_seconds()
            if delta > 0:
                tempo_total += delta

        if tipo in TIPOS_PAUSA:
            relogio_correndo = False
        elif tipo in TIPOS_RETOMADA or tipo == "Reabrir":
            relogio_correndo = True

        ultimo_marcador = data_acao

    if relogio_correndo and ultimo_marcador:
        diff = (datetime.now() - ultimo_marcador).total_seconds()
        if diff > 0:
            tempo_total += diff

    restante = LIMITE_SEGUNDOS - tempo_total
    estourado = tempo_total > LIMITE_SEGUNDOS

    return {
        "inicio": primeira_data.strftime("%d/%m/%Y %H:%M") if primeira_data else "--",
        "tempo_gasto_str": _formatar_segundos(tempo_total),
        "tempo_restante_str": _formatar_segundos(restante),
        "estourado": estourado,
        "mensagem": (
            f"ESTOURADO ha {_formatar_segundos(tempo_total - LIMITE_SEGUNDOS)}"
            if estourado
            else f"RESTAM {_formatar_segundos(restante)}"
        ),
    }


def gerar_sumario(historico: list, resultado: dict) -> str:
    linhas = [
        "RESUMO DO SLA",
        f"  Inicio:       {resultado.get('inicio', '--')}",
        f"  Tempo gasto:  {resultado.get('tempo_gasto_str', '--')}",
        f"  Status:       {resultado.get('mensagem', '--')}",
        f"  Total acoes:  {len(historico)}",
        "",
        "HISTORICO COMPLETO",
        "-" * 40,
    ]
    for acao in reversed(historico):
        linhas.append(
            f"[{acao.get('data', '?')}] {acao.get('tipo', '?')} — {acao.get('autor', '?')}"
        )
        nota = acao.get('descricao', '').strip()
        if nota:
            linhas.append(f"  {nota}")
        linhas.append("")
    return "\n".join(linhas)
