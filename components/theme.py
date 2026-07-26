# ──────────────────────────────────────────────
# Design tokens — medidas em um só lugar.
# Cores: usar rx.color("gray", N) direto nos componentes (theme-aware, claro/escuro).
# ──────────────────────────────────────────────

# Sidebar
SIDEBAR_EXPANDED = "260px"
SIDEBAR_COLLAPSED = "56px"

# Botões — tamanhos do Radix: "1" ~24px, "2" ~32px, "3" ~40px, "4" ~48px.
# Mexer AQUI muda a altura de todos os botões do app de uma vez; as páginas não
# escolhem tamanho, elas escolhem o PAPEL do botão (ver components/botoes.py).
TAMANHO_BOTAO = "2"          # ações de formulário: primário, secundário, perigo
TAMANHO_BOTAO_TABELA = "1"   # botões dentro de linha de tabela (menores de propósito)
