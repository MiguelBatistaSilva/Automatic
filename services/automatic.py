from services.driver_manager import DriverManager
from services.flow_base import execute_generic_flow
from services.kb_manager import executar_kb_unica

# -----------------------------------------------------------------------
# Singleton de modulo — mantém o driver vivo entre execuções.
# Sem isso, quando Automatic() sai de escopo no fim de run_selenium(),
# o GC chama webdriver.Chrome.__del__() → quit() → Chrome fecha.
# -----------------------------------------------------------------------
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

    def executar_fluxo(self, dados_interface):
        """
        Executa o fluxo de automação de forma genérica, mantendo o driver aberto.
        """
        descricao_base = dados_interface['descricao_base']
        kb_config = dados_interface['kb_config']
        df = dados_interface['df']
        numero_chamado = dados_interface['numero_chamado']
        usuario = dados_interface['usuario']
        senha = dados_interface['senha']

        try:
            self.log("Iniciando ou recuperando o WebDriver (Selenium)...", type_log="status")
            driver = self.driver_manager.iniciar_driver_e_navegar()
            self.log("WebDriver pronto. Perfil do Chrome mantido aberto.", type_log="status")

            kb_function = lambda d, l: executar_kb_unica(d, l, kb_config)
            execute_generic_flow(driver, df, descricao_base, numero_chamado, usuario, senha, self.log, kb_function)

        except Exception as e:
            self.log(f"❌ A execução do fluxo FALHOU: {e}", type_log="error")
            return False

        return True
