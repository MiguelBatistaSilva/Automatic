"""
services/fluxos — Cada arquivo é uma ação no Assyst, em Playwright.

Recebem a `page` já logada (services/assyst/browser_pw.py); quem abre o
navegador é o chamador (state/, bot/services/ ou o Assistente).

  flow_requisicao_pw.py      cria Requisição de Serviço do zero
  flow_desmembramento_pw.py  os três modos do Desmembramento
  kb_manager_pw.py           aplica Base de Conhecimento num chamado
  flow_atribuicao_pw.py      Atribuição Interna
  flow_config_fila_pw.py     configura fila (consulta salva do monitor)
  flow_minhafila_pw.py       lê a grade "Minha Fila"
  flow_sla_pw.py             lê o histórico de ações (SLA)
  ações de relógio e texto (menu Ações -> pop-up):
    flow_atendimento_pw.py, flow_programar_pw.py, flow_informacao_pw.py,
    flow_fornecedor_pw.py, flow_usuario_pw.py, flow_info_recebida_pw.py,
    flow_resolver_pw.py
"""
