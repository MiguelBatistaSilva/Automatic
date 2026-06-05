from datetime import datetime, timedelta, time

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
# Tipos que encerram o chamado de vez — param o relogio permanentemente.
TIPOS_FIM = {
    'Resolvido',
    'Fechamento',
}

# Janela de expediente: o relogio so corre entre estas horas, todos os dias.
# Fora dela (madrugada/noite) o relogio congela para qualquer fila.
HORA_INICIO = 8   # 08:00
HORA_FIM = 21     # 21:00

# Configuracao por fila. Extensivel: para adicionar uma nova fila, basta incluir
# uma entrada com o nome EXATO da fila, seu limite em horas e se conta fim de semana.
FILAS = {
    "2N CATI FCB":    {"limite_horas": 3, "conta_fim_de_semana": False},
    "2N CATI Remoto": {"limite_horas": 2, "conta_fim_de_semana": True},
}
FILA_PADRAO = "2N CATI FCB"


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


def _segundos_uteis(inicio: datetime, fim: datetime, conta_fim_de_semana: bool) -> float:
    """
    Conta apenas os segundos do intervalo [inicio, fim] que caem dentro do
    expediente (08:00-21:00). Se conta_fim_de_semana for False, sabados e
    domingos sao totalmente ignorados.
    """
    if fim <= inicio:
        return 0.0

    total = 0.0
    dia = inicio.date()
    ultimo = fim.date()
    while dia <= ultimo:
        # weekday(): segunda=0 ... domingo=6. <5 => dia util (seg-sex).
        if conta_fim_de_semana or dia.weekday() < 5:
            janela_ini = datetime.combine(dia, time(HORA_INICIO, 0, 0))
            janela_fim = datetime.combine(dia, time(HORA_FIM, 0, 0))
            ini = max(inicio, janela_ini)
            f = min(fim, janela_fim)
            if f > ini:
                total += (f - ini).total_seconds()
        dia += timedelta(days=1)
    return total


def calcular_sla(historico: list, fila: str = None) -> dict:
    """
    Calcula o tempo liquido de SLA a partir do historico de acoes do chamado.
    O relogio:
      - so corre dentro do expediente (08:00-21:00);
      - e pausado nos tipos de espera e retomado nos tipos de retomada;
      - para de vez nos tipos de fim (Resolvido/Fechamento);
      - congela aos fins de semana dependendo da fila.
    Retorna um dict com: inicio, tempo_gasto_str, tempo_restante_str,
    estourado, mensagem, fila.
    """
    if not historico:
        return {"estourado": False, "mensagem": "Sem historico para calcular."}

    cfg = FILAS.get(fila, FILAS[FILA_PADRAO])
    limite_segundos = cfg["limite_horas"] * 3600
    conta_fds = cfg["conta_fim_de_semana"]

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
            # Avalia o tipo ja na primeira acao para iniciar pausado se necessario
            if tipo in TIPOS_PAUSA or tipo in TIPOS_FIM:
                relogio_correndo = False
            continue

        if relogio_correndo:
            tempo_total += _segundos_uteis(ultimo_marcador, data_acao, conta_fds)

        if tipo in TIPOS_PAUSA or tipo in TIPOS_FIM:
            relogio_correndo = False
        elif tipo in TIPOS_RETOMADA or tipo == "Reabrir":
            relogio_correndo = True

        ultimo_marcador = data_acao

    # Chamado ainda em andamento: conta do ultimo marcador ate agora.
    if relogio_correndo and ultimo_marcador:
        tempo_total += _segundos_uteis(ultimo_marcador, datetime.now(), conta_fds)

    restante = limite_segundos - tempo_total
    estourado = tempo_total > limite_segundos

    return {
        "inicio": primeira_data.strftime("%d/%m/%Y %H:%M") if primeira_data else "--",
        "tempo_gasto_str": _formatar_segundos(tempo_total),
        "tempo_restante_str": _formatar_segundos(restante),
        "estourado": estourado,
        "fila": fila or FILA_PADRAO,
        "mensagem": (
            f"ESTOURADO há {_formatar_segundos(tempo_total - limite_segundos)}"
            if estourado
            else f"RESTAM {_formatar_segundos(restante)}"
        ),
    }


def gerar_sumario(historico: list, resultado: dict) -> str:
    linhas = [
        "RESUMO DO SLA",
        f"  Fila:         {resultado.get('fila', '--')}",
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
