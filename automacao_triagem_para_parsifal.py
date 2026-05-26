import pandas as pd
import time
import re
from difflib import SequenceMatcher
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# ============================================================
# CONFIGURAÇÕES — edite aqui se necessário
# ============================================================
PARSIFAL_USERNAME = ""
PARSIFAL_PASSWORD = ""
PARSIFAL_REVIEW_URL = ""
PLANILHA = "triagem_1821_completa.csv"
# ============================================================

def limpar_texto(texto):
    """Remove pontuações e excesso de espaços para facilitar a comparação."""
    if pd.isna(texto): return ""
    texto = str(texto).lower()
    texto = re.sub(r'[^a-z0-9]', ' ', texto)
    return " ".join(texto.split())

def encontrar_melhor_match(titulo_parsifal, dict_decisoes, threshold=0.85):
    """Encontra o título no CSV por similaridade ou substring."""
    titulo_p_clean = limpar_texto(titulo_parsifal)
    
    for titulo_csv, decisao in dict_decisoes.items():
        t_csv_clean = limpar_texto(titulo_csv)
        
        # 1. Checagem rápida de Substring
        if (titulo_p_clean in t_csv_clean) or (t_csv_clean in titulo_p_clean):
            return decisao
            
        # 2. Checagem de Similaridade (Fuzzy matching)
        ratio = SequenceMatcher(None, titulo_p_clean, t_csv_clean).ratio()
        if ratio >= threshold:
            return decisao
            
    return None

def carregar_decisoes(arquivo):
    print("Carregando base de dados...")
    df = pd.read_csv(arquivo, encoding="utf-8-sig")
    
    decisoes = {}
    for _, row in df.iterrows():
        titulo = str(row["title"]).strip()
        
        try:
            nota_r1 = float(row.get("round-1_Revisor_Rigoroso_evaluation", 0))
        except: nota_r1 = 0
            
        try:
            nota_r2 = float(row.get("round-2_Especialista_UX_evaluation", 0))
        except: nota_r2 = 0
        
        nota_final = nota_r2 if pd.notna(row.get("round-2_Especialista_UX_evaluation")) else nota_r1
        decisoes[titulo] = "Accepted" if nota_final >= 4 else "Rejected"

    aprovados = sum(1 for v in decisoes.values() if v == "Accepted")
    reprovados = sum(1 for v in decisoes.values() if v == "Rejected")
    print(f"Carregado: {len(decisoes)} artigos | {aprovados} Accepted | {reprovados} Rejected")
    return decisoes

def login(driver, wait):
    print("\nFazendo login no Parsifal...")
    driver.get("https://parsif.al/login/")
    wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(PARSIFAL_USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PARSIFAL_PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    wait.until(EC.url_contains("parsif.al"))
    print("Login concluído com sucesso!")

def classificar_artigos(driver, wait, decisoes):
    print("\nAcessando painel de revisão...")
    driver.get(PARSIFAL_REVIEW_URL)
    
    # Faz o robô esperar inteligentemente até a tabela aparecer na tela
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr .label")))
    except TimeoutException:
        print("Aviso: A tabela demorou muito para carregar.")
        
    time.sleep(2)

    processados = 0
    nao_encontrados = 0
    erros = 0
    titulos_ignorados = set()
    log_erros = []

    while True:
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
            artigo_clicado_neste_ciclo = False

            for row in rows:
                titulo_pagina = "Desconhecido"
                try:
                    # CORREÇÃO: Busca as labels como uma lista. Se a linha estiver vazia, ele ignora sem dar erro.
                    badges = row.find_elements(By.CSS_SELECTOR, ".label")
                    if not badges:
                        continue # Pula esta linha silenciosamente
                    
                    badge = badges[0]
                    if "Unclassified" not in badge.text:
                        continue

                    # O Título fica no 3º TD (índice 2)
                    tds = row.find_elements(By.TAG_NAME, "td")
                    if len(tds) < 3: continue
                        
                    titulo_elem = tds[2]
                    titulo_pagina = titulo_elem.text.strip()

                    if titulo_pagina in titulos_ignorados:
                        continue

                    decisao = encontrar_melhor_match(titulo_pagina, decisoes)

                    if decisao is None:
                        nao_encontrados += 1
                        titulos_ignorados.add(titulo_pagina)
                        log_erros.append(f"NÃO ENCONTRADO NA PLANILHA: {titulo_pagina}")
                        print(f"[Aviso] Título ausente no CSV (marcado para pular): {titulo_pagina[:50]}...")
                        continue

                    # ==================================================
                    # INTERAÇÃO COM O MODAL ESPECÍFICO
                    # ==================================================
                    
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", titulo_elem)
                    time.sleep(0.3)
                    
                    try:
                        titulo_elem.click()
                    except ElementClickInterceptedException:
                        driver.execute_script("arguments[0].click();", titulo_elem)
                    
                    modal = wait.until(EC.visibility_of_element_located((By.ID, "modal-article")))
                    time.sleep(1)
                    
                    select_elem = modal.find_element(By.ID, "status")
                    status_select = Select(select_elem)
                    status_select.select_by_visible_text(decisao)
                    
                    save_btn = modal.find_element(By.CSS_SELECTOR, ".btn-save-article")
                    save_btn.click()
                    time.sleep(0.8)
                    
                    close_btn = modal.find_element(By.XPATH, ".//button[text()='Close']")
                    close_btn.click()
                    
                    wait.until(EC.invisibility_of_element_located((By.ID, "modal-article")))
                    time.sleep(0.5)

                    processados += 1
                    artigo_clicado_neste_ciclo = True
                    titulos_ignorados.add(titulo_pagina)

                    if processados % 5 == 0:
                        print(f"Progresso: {processados} classificados | {erros} erros de clique | {nao_encontrados} ausentes no CSV")

                    # === MODO DE TESTE (pode comentar/apagar depois de validar) ===
                    # if processados >= 5:
                    #     print("\n[TESTE] Limite de 5 artigos atingido! Finalizando...")
                    #     return 
                    # ===============================================================

                    break

                except Exception as e:
                    erros += 1
                    erro_str = str(e).split('\n')[0]
                    log_erros.append(f"ERRO ({erro_str}): {titulo_pagina}")
                    print(f"Erro ao interagir com '{titulo_pagina[:50]}': {erro_str}")
                    
                    try:
                        modal_aberto = driver.find_element(By.ID, "modal-article")
                        if modal_aberto.is_displayed():
                            fechar = modal_aberto.find_element(By.XPATH, ".//button[text()='Close'] | .//button[@class='close']")
                            driver.execute_script("arguments[0].click();", fechar)
                            time.sleep(1)
                    except:
                        pass
                    
                    titulos_ignorados.add(titulo_pagina)
                    continue

            if not artigo_clicado_neste_ciclo:
                print("\nNenhum artigo 'Unclassified' mapeável restante na tela atual.")
                break

        except Exception as e:
            print(f"Erro geral recarregando a página: {e}")
            erros += 1
            driver.refresh()
            time.sleep(5)

    if log_erros:
        with open("log_automacao.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(log_erros))
        print(f"\nLog de discrepâncias salvo em log_automacao.txt")

    print(f"\n✅ RESUMO FINAL:")
    print(f"   Classificados com sucesso:  {processados}")
    print(f"   Não encontrados no CSV:     {nao_encontrados}")
    print(f"   Erros de tela:              {erros}")

def main():
    options = webdriver.ChromeOptions()
    
    # --- Configurações do modo invisível ---
    options.add_argument("--headless") # Ativa o modo invisível
    options.add_argument("--window-size=1920,1080") # Força resolução de monitor grande para não quebrar o layout
    # ---------------------------------------
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 10)

    try:
        decisoes = carregar_decisoes(PLANILHA)
        login(driver, wait)
        classificar_artigos(driver, wait, decisoes)
    finally:
        print("\nProcesso concluído. Fechando navegador.")
        time.sleep(3)
        driver.quit()

if __name__ == "__main__":
    main()