"""
AUTOMAÇÃO — DATA EXTRACTION NO PARSIFAL (v1)
=============================================
Lê o CSV resultante da extração de dados (extracao_completa.csv) e preenche
automaticamente os 14 campos de cada artigo na página de Data Extraction do Parsifal.

Campos do Parsifal:
  1.  Objetivo Principal do Estudo              → textarea
  2.  Contexto da Avaliação                     → textarea
  3.  Duração do Estudo Longitudinal            → textarea
  4.  Número de Participantes                   → textarea
  5.  Tipo de Abordagem de Avaliação            → SELECT (Continua / Híbrida/Ambas / Retrospectiva)
  6.  Nome do Método/Técnica/Ferramenta         → textarea
  7.  Descrição da Abordagem                    → textarea
  8.  Vantagens/Benefícios Reportados           → textarea
  9.  Desvantagens/Limitações/Desafios          → textarea
  10. Métricas de Coleta de Dados Utilizadas    → textarea
  11. Técnicas de Análise de Dados Utilizadas   → textarea
  12. Formas de Visualização dos Dados          → textarea
  13. Vestígios, ideias ou indícios p/ futuros  → textarea
  14. Comentários adicionais                    → textarea

O conteúdo enviado para cada textarea é:
    [síntese interpretativa]
    [Trecho do artigo]: "trecho literal copiado do artigo"

COMO USAR:
    pip install selenium webdriver-manager pandas
    python automacao_extracao_parsifal.py

Para rodar todos: mude LIMITE_TESTE = None
"""

import time
import re
import pandas as pd
from pathlib import Path
from difflib import SequenceMatcher

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, StaleElementReferenceException
)
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# ===========================================================================
# CONFIGURAÇÕES
# ===========================================================================
PARSIFAL_USERNAME     = ""
PARSIFAL_PASSWORD     = ""
PARSIFAL_EXTRACAO_URL = (
    ""
)

CSV_EXTRACAO      = r"extracao/extracao_completa.csv"
SIMILARIDADE_MIN  = 0.82
DELAY_ARTIGOS     = 2.0
DELAY_CAMPOS      = 0.4

# ⚠️ MODO TESTE: processa apenas os primeiros N artigos
# Mude para None para rodar TODOS os 64
LIMITE_TESTE = None

# Mapeamento: coluna CSV → índice do campo no Parsifal (ordem visual dos textareas)
# O select (tipo_abordagem) é tratado separadamente
MAPA_CAMPOS = {
    # coluna_sintese           : índice (0-based) do textarea no Parsifal
    "objetivo_principal"    : 0,
    "contexto_avaliacao"    : 1,
    "duracao_estudo"        : 2,
    "numero_participantes"  : 3,
    # índice 4 = SELECT (tipo_abordagem) — tratado separadamente
    "nome_metodo"           : 4,   # 5º textarea (após o select)
    "descricao_abordagem"   : 5,
    "vantagens"             : 6,
    "desvantagens"          : 7,
    "metricas_coleta"       : 8,
    "tecnicas_analise"      : 9,
    "visualizacao_dados"    : 10,
    "trabalhos_futuros"     : 11,
    "comentarios_adicionais": 12,
}

# Mapeamento do valor CSV para o texto da opção no select do Parsifal
MAPA_SELECT = {
    "continua"      : "Continua",
    "retrospectiva" : "Retrospectiva",
    "hibrida/ambas" : "Híbrida/Ambas",
    "híbrida/ambas" : "Híbrida/Ambas",
}
# ===========================================================================


def limpar_texto(t: str) -> str:
    return re.sub(r'[^a-z0-9]', ' ', str(t).lower()).split()


def similaridade(a: str, b: str) -> float:
    return SequenceMatcher(None, ' '.join(limpar_texto(a)), ' '.join(limpar_texto(b))).ratio()


def buscar_no_csv(titulo_parsifal: str, df: pd.DataFrame):
    """Retorna a linha do CSV mais similar ao título do Parsifal."""
    tp = ' '.join(limpar_texto(titulo_parsifal))
    best_s, best_r = 0.0, None
    for _, row in df.iterrows():
        tc = ' '.join(limpar_texto(str(row.get("titulo", ""))))
        if not tc:
            continue
        if tp in tc or tc in tp:
            return row
        s = SequenceMatcher(None, tp, tc).ratio()
        if s > best_s:
            best_s, best_r = s, row
    return best_r if best_s >= SIMILARIDADE_MIN else None


def montar_conteudo(row: pd.Series, campo: str) -> str:
    """
    Monta o texto que vai no textarea:
    síntese + trecho literal (quando disponível).
    """
    sintese = str(row.get(campo, "")).strip()
    trecho  = str(row.get(f"{campo}_trecho", "")).strip()

    if not sintese or sintese.lower() in ("nan", ""):
        sintese = "Não informado"
    if not trecho or trecho.lower() in ("nan", "não encontrado no artigo", ""):
        trecho = "Não encontrado no artigo"

    if trecho == "Não encontrado no artigo":
        return sintese
    return f"{sintese}\n\n[Trecho do artigo]: {trecho}"


def login(driver, wait):
    print("\nFazendo login...")
    driver.get("https://parsif.al/login/")
    wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(PARSIFAL_USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PARSIFAL_PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    wait.until(EC.url_contains("parsif.al"))
    print("Login OK!")


def preencher_textarea(driver, textarea_elem, texto: str):
    """Limpa e preenche um textarea com o texto fornecido."""
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", textarea_elem)
    time.sleep(0.15)
    driver.execute_script("arguments[0].value = '';", textarea_elem)
    driver.execute_script("arguments[0].value = arguments[1];", textarea_elem, texto)
    # dispara evento de change para o Parsifal reconhecer a alteração
    driver.execute_script(
        "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
        textarea_elem
    )
    time.sleep(0.1)


def preencher_select(driver, select_elem, valor_csv: str) -> bool:
    """Seleciona a opção correta no dropdown de tipo_abordagem."""
    valor_normalizado = valor_csv.strip().lower()
    texto_opcao = MAPA_SELECT.get(valor_normalizado)
    if not texto_opcao:
        print(f"    ⚠ tipo_abordagem desconhecido: '{valor_csv}' — deixando em branco")
        return False
    try:
        sel = Select(select_elem)
        sel.select_by_visible_text(texto_opcao)
        return True
    except Exception as e:
        # Tenta por valor parcial
        try:
            opcoes = select_elem.find_elements(By.TAG_NAME, "option")
            for op in opcoes:
                if texto_opcao.lower() in op.text.lower():
                    op.click()
                    return True
        except Exception:
            pass
        print(f"    ⚠ Erro ao selecionar '{texto_opcao}': {e}")
        return False


def artigo_ja_preenchido(painel) -> bool:
    """
    Verifica se o artigo já foi marcado como 'done' no Parsifal.
    O botão 'mark as done' muda de aparência quando marcado.
    """
    try:
        botao = painel.find_element(By.CSS_SELECTOR, "a.mark-as-done, input[type='checkbox']")
        classes = botao.get_attribute("class") or ""
        # Se tiver classe 'done', 'checked' ou similar, já foi preenchido
        if any(c in classes for c in ["done", "checked", "active"]):
            return True
        # Verifica se o primeiro textarea já tem conteúdo
        textareas = painel.find_elements(By.TAG_NAME, "textarea")
        if textareas and textareas[0].get_attribute("value"):
            return True
    except Exception:
        pass
    return False


def preencher_artigo(driver, painel, row: pd.Series) -> tuple[int, int, list]:
    """
    Preenche todos os campos de um artigo no Parsifal.
    Retorna (campos_ok, campos_falha, detalhes_falhas).
    """
    ok, falha, detalhes = 0, 0, []

    # Coleta todos os textareas do painel
    textareas = painel.find_elements(By.TAG_NAME, "textarea")
    # Coleta o select (tipo_abordagem)
    selects   = painel.find_elements(By.TAG_NAME, "select")

    # ── Preenche textareas ────────────────────────────────────────────────
    for campo, idx in MAPA_CAMPOS.items():
        if idx >= len(textareas):
            falha += 1
            detalhes.append(f"{campo}: textarea[{idx}] não encontrado (total={len(textareas)})")
            continue
        texto = montar_conteudo(row, campo)
        try:
            preencher_textarea(driver, textareas[idx], texto)
            ok += 1
        except Exception as e:
            falha += 1
            detalhes.append(f"{campo}: erro ao preencher — {str(e)[:60]}")
        time.sleep(DELAY_CAMPOS)

    # ── Preenche select (tipo_abordagem) ──────────────────────────────────
    if selects:
        valor_tipo = str(row.get("tipo_abordagem", "")).strip()
        sucesso = preencher_select(driver, selects[0], valor_tipo)
        if sucesso:
            ok += 1
        else:
            falha += 1
            detalhes.append(f"tipo_abordagem: falha no select (valor='{valor_tipo}')")
    else:
        falha += 1
        detalhes.append("tipo_abordagem: select não encontrado no painel")

    time.sleep(DELAY_CAMPOS)

    # ── Salva clicando fora do painel (trigger de auto-save do Parsifal) ──
    try:
        driver.execute_script("document.activeElement.blur();")
        time.sleep(0.5)
    except Exception:
        pass

    return ok, falha, detalhes


def executar(driver, wait, df: pd.DataFrame):
    print(f"\nAbrindo Data Extraction...")
    driver.get(PARSIFAL_EXTRACAO_URL)
    time.sleep(3)

    # Garante que estamos na aba "To-do" ou "All"
    try:
        btn_all = driver.find_element(By.LINK_TEXT, "All")
        btn_all.click()
        time.sleep(1.5)
        print("Filtro 'All' ativado.")
    except NoSuchElementException:
        print("Filtro 'All' não encontrado, continuando na aba atual.")

    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "textarea")))
    except TimeoutException:
        print("Aviso: textareas demoraram para aparecer.")
    time.sleep(2)

    if LIMITE_TESTE is not None:
        print(f"\n{'*'*55}")
        print(f"*** MODO TESTE: processando apenas {LIMITE_TESTE} artigos ***")
        print(f"*** Para rodar todos: mude LIMITE_TESTE = None           ***")
        print(f"{'*'*55}\n")

    # Cada artigo fica num div/panel separado com o título e os campos
    # Parsifal usa estrutura: div com h4/h5 de título + campos abaixo
    paineis = driver.find_elements(
        By.CSS_SELECTOR,
        "div.extraction-study, div.study-extraction, div[class*='study'], div[class*='extraction']"
    )

    # Fallback: busca por elementos que contêm textarea e título
    if not paineis:
        paineis = driver.find_elements(By.CSS_SELECTOR, "div.panel, div.card")

    print(f"Painéis encontrados: {len(paineis)}")

    processados = nao_encontrados = erros = pulados = 0
    ja_feitos   = set()
    log         = []

    for painel in paineis:
        if LIMITE_TESTE is not None and processados >= LIMITE_TESTE:
            print(f"\n[TESTE] Limite de {LIMITE_TESTE} artigos atingido. Encerrando.")
            break

        titulo_parsifal = ""
        try:
            # Tenta extrair o título do painel
            for seletor in ["h4", "h5", "h3", "span.study-title", "a.study-title", ".panel-title"]:
                try:
                    elem_titulo = painel.find_element(By.CSS_SELECTOR, seletor)
                    titulo_parsifal = re.sub(r'\s*\(\d{4}\)\s*$', '', elem_titulo.text).strip()
                    if len(titulo_parsifal) > 10:
                        break
                except NoSuchElementException:
                    continue

            if not titulo_parsifal or titulo_parsifal in ja_feitos:
                continue

            # Verifica se já foi preenchido
            if artigo_ja_preenchido(painel):
                pulados += 1
                ja_feitos.add(titulo_parsifal)
                print(f"  — [PRONTO] {titulo_parsifal[:65]}... (pulado)")
                continue

            # Busca no CSV
            row = buscar_no_csv(titulo_parsifal, df)
            if row is None:
                nao_encontrados += 1
                ja_feitos.add(titulo_parsifal)
                log.append(f"NAO ENCONTRADO: {titulo_parsifal}")
                print(f"  [?] Não encontrado no CSV: {titulo_parsifal[:65]}...")
                continue

            # Verifica se extração foi OK (não revisar artigos com falha total)
            status = str(row.get("status", "")).strip().upper()
            if status == "REVISAR":
                print(f"  [⚠] REVISÃO MANUAL: {titulo_parsifal[:55]}... (status=REVISAR, pulando)")
                log.append(f"REVISAO_MANUAL: {titulo_parsifal}")
                ja_feitos.add(titulo_parsifal)
                continue

            # Preenche os campos
            ok, falha, detalhes = preencher_artigo(driver, painel, row)
            processados += 1
            ja_feitos.add(titulo_parsifal)

            status_str = "OK" if falha == 0 else "AV"
            print(
                f"  [{status_str}] [{processados:03d}] {titulo_parsifal[:52]:<52}"
                f" | campos ok:{ok:2}/14"
                + (f" | falhas:{detalhes}" if detalhes else "")
            )
            if detalhes:
                log.append(f"FALHAS ({titulo_parsifal}): {detalhes}")

            time.sleep(DELAY_ARTIGOS)

        except StaleElementReferenceException:
            erros += 1
            ja_feitos.add(titulo_parsifal)
            log.append(f"STALE: {titulo_parsifal}")
        except Exception as e:
            erros += 1
            ja_feitos.add(titulo_parsifal)
            msg = str(e).split('\n')[0]
            log.append(f"ERRO ({msg[:60]}): {titulo_parsifal}")
            print(f"  [!] Erro: {msg[:80]}")

    if log:
        Path("log_extracao_parsifal.txt").write_text("\n".join(log), encoding="utf-8")
        print(f"\nLog salvo em: log_extracao_parsifal.txt")

    print(f"\n{'='*55}")
    print(f"RESUMO FINAL")
    print(f"  Preenchidos            : {processados}")
    print(f"  Já prontos (pulados)   : {pulados}")
    print(f"  Não encontrados no CSV : {nao_encontrados}")
    print(f"  Erros                  : {erros}")
    if LIMITE_TESTE is not None and processados >= LIMITE_TESTE:
        print(f"\n  MODO TESTE concluído: {LIMITE_TESTE} artigos processados.")
        print(f"  Para rodar todos: mude LIMITE_TESTE = None no topo do arquivo.")
    print(f"{'='*55}")


def carregar_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    print(f"  CSV carregado: {len(df)} artigos")
    ok      = (df["status"].str.upper() == "OK").sum()
    revisar = (df["status"].str.upper() == "REVISAR").sum()
    print(f"  Status OK     : {ok}")
    print(f"  Status REVISAR: {revisar} (serão pulados — revisar manualmente)")
    return df


def main():
    print("=" * 55)
    print("AUTOMAÇÃO — DATA EXTRACTION NO PARSIFAL")
    print(f"Modo: {'TESTE (' + str(LIMITE_TESTE) + ' artigos)' if LIMITE_TESTE else 'COMPLETO (todos)'}")
    print("=" * 55)

    print("\nCarregando CSV...")
    df = carregar_csv(CSV_EXTRACAO)
    if df.empty:
        print("CSV vazio ou não encontrado.")
        return

    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # descomente para rodar invisível
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    wait = WebDriverWait(driver, 20)

    try:
        login(driver, wait)
        executar(driver, wait, df)
    finally:
        print("\nFechando navegador...")
        time.sleep(2)
        driver.quit()


if __name__ == "__main__":
    main()