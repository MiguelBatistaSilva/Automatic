"""
components/log_console.py — Console de logs em tempo real.

Renderiza a lista `logs` (dicts {ts, tipo, msg}) do FlowRunnerState, colorindo
cada linha por `tipo`. Equivalente ao QTextEdit + QTextCharFormat do PyQt6.
"""

import reflex as rx


def _linha(item: rx.Var) -> rx.Component:
    return rx.text(
        f"[{item.ts}] {item.msg}",
        color=rx.match(
            item.tipo,
            ("success", "#16A34A"),
            ("error", "#DC2626"),
            ("status", "#0891B2"),
            "#6B7280",  # info / default
        ),
        font_family="monospace",
        font_size="0.85em",
        white_space="pre-wrap",
        margin="0",
    )


def log_console(logs: rx.Var) -> rx.Component:
    return rx.box(
        rx.foreach(logs, _linha),
        height="340px",
        width="100%",
        overflow_y="auto",
        padding="0.75em",
        border="1px solid #D1D5DB",
        border_radius="6px",
        background="#F9FAFB",
    )
