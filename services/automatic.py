from services.driver_manager import DriverManager
from services.flow_base import execute_generic_flow
from services.kb_manager import executar_kb_unica

_driver_manager_singleton: DriverManager | None = None


def _get_driver_manager(log_func) -> DriverManager:
    global _driver_manager_singleton
    if _driver_manager_singleton is None:
        _driver_manager_singleton = DriverManager(log_func)
    else:
        _driver_manager_singleton.log = log_func
    return _driver_manager_singleton


class Automatic:

    def __init__(self, log_func):
        self.log = log_func
        self.driver_manager = _get_driver_manager(log_func)

    def executar_fluxo(self, dados_interface, iniciar_do_zero: bool = False):
        descricao_base  = dados_interface['descricao_base']
        kb_config       = dados_interface['kb_config']
        df              = dados_interface['df']
        numero_chamado  = dados_interface['numero_chamado']
        usuario         = dados_interface['usuario']
        senha           = dados_interface['senha']

        try:
            self.log("Iniciando ou recuperando o WebDriver...", "status")
            driver = self.driver_manager.iniciar_driver_e_navegar()
            self.log("WebDriver pronto.", "status")

            kb_function = lambda d, l: executar_kb_unica(d, l, kb_config)
            execute_generic_flow(
                driver, df, descricao_base, numero_chamado,
                usuario, senha, self.log, kb_function,
                iniciar_do_zero=iniciar_do_zero,
            )

        except Exception as e:
            self.log(f"A execucao FALHOU: {e}", "error")
            return False

        return True