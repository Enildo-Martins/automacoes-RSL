import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

PARSIFAL_USERNAME = ""
PARSIFAL_PASSWORD = ""
PARSIFAL_REVIEW_URL = ""

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)
wait = WebDriverWait(driver, 15)

# Login
driver.get("https://parsif.al/login/")
wait.until(EC.presence_of_element_located((By.NAME, "username")))
driver.find_element(By.NAME, "username").send_keys(PARSIFAL_USERNAME)
driver.find_element(By.NAME, "password").send_keys(PARSIFAL_PASSWORD)
driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
time.sleep(3)

# Vai para study selection
driver.get(PARSIFAL_REVIEW_URL)
time.sleep(3)

# Salva HTML da lista de artigos
with open("pagina_lista.html", "w", encoding="utf-8") as f:
    f.write(driver.page_source)
print("HTML da lista salvo em pagina_lista.html")

# Tira screenshot da lista
driver.save_screenshot("screenshot_lista.png")
print("Screenshot salvo em screenshot_lista.png")

# Tenta clicar no primeiro artigo da tabela
try:
    primeira_linha = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")[0]
    print(f"\nHTML da primeira linha:\n{primeira_linha.get_attribute('outerHTML')[:1000]}")
    
    # Clica no título
    primeira_linha.find_elements(By.TAG_NAME, "td")[2].click()
    time.sleep(2)
    
    # Salva HTML do modal
    with open("pagina_modal.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print("HTML do modal salvo em pagina_modal.html")
    driver.save_screenshot("screenshot_modal.png")
    print("Screenshot do modal salvo em screenshot_modal.png")

except Exception as e:
    print(f"Erro: {e}")

input("\nPressione Enter para fechar o Chrome...")
driver.quit()