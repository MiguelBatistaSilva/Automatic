from selenium.webdriver.common.by import By

# --- LOCATORS DA TELA DE LOGIN  ---
selector_username = (By.NAME, "j_username")
selector_password = (By.NAME, "j_password")
selector_login = (By.ID,"loginSubmit")

usuario_afetado = (By.ID, "ManageEventForm_ES3_affectedUser_textNode")
resumo_selector = (By.ID, "ManageEventForm_ES3_shortDescription")
descricao_iframe = (By.XPATH, "//iframe[contains(@title, 'rtES3_formattedRemarks')]")
descricao_body = (By.CSS_SELECTOR, "body.cke_editable")


selector_filter_icon = (By.CSS_SELECTOR, ".dijitIcon.filterIcon")
selector_popup = (By.XPATH, "//span[contains(@class, 'dijitDialogTitle') and contains(text(), 'Critério de pesquisa')]")

# --- LOCATORS DA TELA DE PESQUISA  ---
selector_department = (By.ID, "EventSearchForm_NONE_event_lookup_actioningServiceDepartment_textNode")
selector_datede = (By.ID, "txt_event.lookup.dateActionedFromDate")
selector_horade = (By.ID, "txt_event.lookup.dateActionedFromTime")
selector_dateate = (By.ID, "txt_event.lookup.dateActionedToDate")
selector_horaate = (By.ID, "txt_event.lookup.dateActionedToTime")

selector_ok = (By.XPATH, "//span[text()='OK']")

# --- LOCATORS DA TABELA DE RESULTADOS ---
selector_lines = (By.CSS_SELECTOR, ".dojoxGridRow")
selector_scroll = (By.CSS_SELECTOR, ".dojoxGridScrollbox")

# --- CAMPOS ---
selector_item = (By.CLASS_NAME, "itemA_nameCell")
selector_categoria = (By.CLASS_NAME, "category_nameCell")
selector_usuarior = (By.CLASS_NAME, "lastResolvingUser_nameCell")
selector_dps = (By.CLASS_NAME, "lastResolvingServDept_nameCell")