from selenium.webdriver.common.by import By

usuario_afetado = (By.ID, "ManageEventForm_ES3_affectedUser_textNode")

resumo_selector = (By.ID, "ManageEventForm_ES3_shortDescription")

descricao_iframe = (By.XPATH, "//iframe[contains(@title, 'rtES3_formattedRemarks')]")
descricao_body = (By.CSS_SELECTOR, "body.cke_editable")

produto_selector = (By.ID, "ManageEventForm_ES3_itemAProduct_textNode")
item_selector = (By.ID, "ManageEventForm_ES3_itemA_textNode")
produto_b = (By.ID, "ManageEventForm_ES3_itemBProduct_textNode")
item_b = (By.ID, "ManageEventForm_ES3_itemB_textNode")
categoria_selector = (By.ID, "ManageEventForm_ES3_eventBuilder_textNode")

grupo_atribuido = (By.ID, "ManageEventForm_ES3_assignedServDept_textNode")
usuario_atribuido_selector = (By.ID, "ManageEventForm_ES3_assignee_textNode")

disquete = (By.ID, "btlogEvent")
duplicar = (By.ID, "btlogAsNewEvent")
continuar_xpath = (By.XPATH, "//span[text()='Continuar']/ancestor::span[contains(@role, 'button')]")
