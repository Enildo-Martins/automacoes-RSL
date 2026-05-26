"""
AUTOMAÇÃO — QUALITY ASSESSMENT NO PARSIFAL (v2)
Atualizado para 9 questões (protocolo revisado) e envia TODOS os 144 artigos.
O Parsifal define o corte internamente — aqui mandamos tudo sem filtrar.

Seletores baseados no HTML real:
  - Título:   h3.panel-title
  - Tabela:   table#tbl-quality
  - Questões: tr[question-id]
  - Botões:   td.answer com texto "Sim" / "Parcial" / "Não"
"""

import time, re
import pandas as pd
from pathlib import Path
from difflib import SequenceMatcher

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, StaleElementReferenceException
)
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ===========================================================================
PARSIFAL_USERNAME    = ""
PARSIFAL_PASSWORD    = ""
PARSIFAL_QUALITY_URL = (
    ""
)

# CSV atualizado (gerado a partir do Excel com avaliações manuais incluídas)
CSV_CONSOLIDADO = r"qualidade/consolidado_final_164.csv"

SIMILARIDADE_MINIMA = 0.82
DELAY_ENTRE_ARTIGOS = 1.2
DELAY_ENTRE_CLIQUES = 0.35

# 9 questões (protocolo v2)
MAPA_QUESTOES = {
    "q1": 1, "q2": 2, "q3": 3, "q4": 4, "q5": 5,
    "q6": 6, "q7": 7, "q8": 8, "q9": 9,
}

MAPA_CLIQUE = {
    "SIM": "Sim", "PARCIAL": "Parcial",
    "NÃO": "Não", "NAO": "Não", "": "Não",
}

NUM_QUESTOES = 9

# Limite para teste — mude para None para rodar TODOS
LIMITE_TESTE = None
# ===========================================================================

def limpar(t):
    t = re.sub(r'[^a-z0-9]', ' ', str(t).lower())
    return " ".join(t.split())

def match(titulo_p, df):
    tp = limpar(titulo_p)
    best_s, best_r = 0.0, None
    for _, row in df.iterrows():
        tc = limpar(str(row.get("titulo", "") or ""))
        if not tc:
            continue
        if tp in tc or tc in tp:
            return row
        s = SequenceMatcher(None, tp, tc).ratio()
        if s > best_s:
            best_s, best_r = s, row
    return best_r if best_s >= SIMILARIDADE_MINIMA else None

def carregar_csv(path):
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    print(f"  Total no CSV: {len(df)} artigos — todos serao enviados ao Parsifal")
    scores = pd.to_numeric(df["score_total"], errors="coerce")
    ap = (scores >= 6.5).sum()
    print(f"  Aprovados (score >= 6.5): {ap}")
    print(f"  Reprovados              : {len(df) - ap}")
    return df

def login(driver, wait):
    print("\nFazendo login...")
    driver.get("https://parsif.al/login/")
    wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(PARSIFAL_USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PARSIFAL_PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    wait.until(EC.url_contains("parsif.al"))
    print("Login OK!")

def artigo_completamente_preenchido(tabela_elem):
    try:
        marcados = tabela_elem.find_elements(
            By.XPATH,
            ".//td[contains(@class,'answer') and "
            "(contains(@class,'success') or contains(@class,'selected') or "
            "contains(@class,'active') or contains(@class,'warning') or "
            "contains(@class,'danger') or @style)]"
        )
        return len(marcados) == NUM_QUESTOES
    except Exception:
        return False

def clicar_resposta(driver, tr_elem, resposta_csv):
    texto_alvo = MAPA_CLIQUE.get(resposta_csv.strip().upper(), "Não")
    try:
        td = tr_elem.find_element(
            By.XPATH,
            f".//td[contains(@class,'answer') and normalize-space(text())='{texto_alvo}']"
        )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", td)
        time.sleep(0.15)
        try:
            td.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", td)
        return True
    except NoSuchElementException:
        return False

def preencher_artigo(driver, tabela_elem, linha_csv):
    trs = tabela_elem.find_elements(By.CSS_SELECTOR, "tr[question-id]")
    ok, falha, detalhes = 0, 0, []

    for col_csv, num_q in MAPA_QUESTOES.items():
        resposta = str(linha_csv.get(col_csv, "NÃO")).strip().upper()
        if not resposta or resposta == "NAN":
            resposta = "NÃO"

        idx = num_q - 1
        if idx >= len(trs):
            falha += 1
            detalhes.append(f"Q{num_q}:sem tr (total={len(trs)})")
            continue

        sucesso = clicar_resposta(driver, trs[idx], resposta)
        if sucesso:
            ok += 1
        else:
            falha += 1
            detalhes.append(f"Q{num_q}:td.answer nao encontrado")
        time.sleep(DELAY_ENTRE_CLIQUES)

    return ok, falha, detalhes

def ativar_filtro_all(driver):
    try:
        for sel in ["input#all-filter", "input[value='all']", "input[id*='all']"]:
            try:
                radio = driver.find_element(By.CSS_SELECTOR, sel)
                driver.execute_script("arguments[0].click();", radio)
                time.sleep(1.5)
                print("Filtro 'All' ativado.")
                return
            except NoSuchElementException:
                continue
        for label in driver.find_elements(By.CSS_SELECTOR, "label"):
            if label.text.strip() == "All":
                driver.execute_script("arguments[0].click();", label)
                time.sleep(1.5)
                print("Filtro 'All' ativado via label.")
                return
        print("Aviso: nao encontrou filtro 'All', continuando mesmo assim.")
    except Exception as e:
        print(f"Aviso ao ativar filtro All: {e}")

def executar(driver, wait, df):
    print(f"\nAbrindo Quality Assessment...")
    driver.get(PARSIFAL_QUALITY_URL)
    time.sleep(3)

    ativar_filtro_all(driver)

    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table#tbl-quality")))
    except TimeoutException:
        print("Aviso: tabelas demoraram para carregar.")
    time.sleep(2)

    if LIMITE_TESTE is not None:
        print(f"*** MODO TESTE: limitado a {LIMITE_TESTE} artigos ***")
        print(f"    Para rodar todos, mude LIMITE_TESTE = None\n")

    processados = nao_encontrados = erros = pulados_completos = 0
    ja_feitos = set()
    log = []

    paineis = driver.find_elements(By.CSS_SELECTOR, "div.panel-quality-assessment")
    print(f"Paineis encontrados: {len(paineis)}\n")

    for painel in paineis:
        if LIMITE_TESTE is not None and processados >= LIMITE_TESTE:
            print(f"\n[TESTE] Limite de {LIMITE_TESTE} artigos atingido. Encerrando.")
            break

        titulo_parsifal = ""
        try:
            h3 = painel.find_element(By.CSS_SELECTOR, "h3.panel-title")
            titulo_parsifal = re.sub(r'\s*\(\d{4}\)\s*$', '', h3.text).strip()
            if not titulo_parsifal or titulo_parsifal in ja_feitos:
                continue

            try:
                tabela = painel.find_element(By.CSS_SELECTOR, "table#tbl-quality")
            except NoSuchElementException:
                erros += 1
                log.append(f"SEM TABELA: {titulo_parsifal}")
                ja_feitos.add(titulo_parsifal)
                continue

            if artigo_completamente_preenchido(tabela):
                pulados_completos += 1
                ja_feitos.add(titulo_parsifal)
                print(f"  - [COMPLETO] {titulo_parsifal[:65]}... (pulado)")
                continue

            linha_csv = match(titulo_parsifal, df)
            if linha_csv is None:
                nao_encontrados += 1
                ja_feitos.add(titulo_parsifal)
                log.append(f"NAO ENCONTRADO: {titulo_parsifal}")
                print(f"  [?] Nao encontrado: {titulo_parsifal[:65]}...")
                continue

            ok, falha, detalhes = preencher_artigo(driver, tabela, linha_csv)
            processados += 1
            ja_feitos.add(titulo_parsifal)

            status = "OK" if falha == 0 else "AV"
            score  = linha_csv.get("score_total", "?")
            aprov  = linha_csv.get("aprovado", "?")
            print(
                f"  [{status}] [{processados:03d}] {titulo_parsifal[:50]:<50}"
                f" | score:{score:>4} | {aprov}"
                + (f" | Falhas:{detalhes}" if detalhes else "")
            )
            if detalhes:
                log.append(f"FALHAS ({titulo_parsifal}): {detalhes}")
            time.sleep(DELAY_ENTRE_ARTIGOS)

        except StaleElementReferenceException:
            erros += 1
            ja_feitos.add(titulo_parsifal)
        except Exception as e:
            erros += 1
            ja_feitos.add(titulo_parsifal)
            msg = str(e).split('\n')[0]
            log.append(f"ERRO ({msg}): {titulo_parsifal}")
            print(f"  [!] Erro: {msg[:80]}")

    if log:
        Path("log_qualidade_parsifal_v2.txt").write_text("\n".join(log), encoding="utf-8")
        print(f"\nLog salvo em: log_qualidade_parsifal_v2.txt")

    print(f"\n{'='*55}")
    print(f"RESUMO FINAL")
    print(f"  Preenchidos            : {processados}")
    print(f"  Ja completos (pulados) : {pulados_completos}")
    print(f"  Nao encontrados no CSV : {nao_encontrados}")
    print(f"  Erros                  : {erros}")
    if LIMITE_TESTE is not None and processados >= LIMITE_TESTE:
        print(f"\n  MODO TESTE: apenas {LIMITE_TESTE} artigos processados.")
        print(f"  Para rodar todos: mude LIMITE_TESTE = None no topo.")
    print(f"{'='*55}")

def main():
    print("=" * 55)
    print("AUTOMACAO — QUALITY ASSESSMENT NO PARSIFAL (v2)")
    print("9 questoes | Todos os 144 artigos")
    print("=" * 55)
    print("\nCarregando CSV...")
    df = carregar_csv(CSV_CONSOLIDADO)
    if df.empty:
        print("CSV vazio ou nao encontrado.")
        return

    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # descomente para rodar invisivel
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    wait = WebDriverWait(driver, 15)
    try:
        login(driver, wait)
        executar(driver, wait, df)
    finally:
        print("\nFechando navegador...")
        time.sleep(2)
        driver.quit()

if __name__ == "__main__":
    main()