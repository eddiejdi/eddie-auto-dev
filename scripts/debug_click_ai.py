from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

opts = Options()
opts.add_argument('--headless')
opts.add_argument('--no-sandbox')
opts.add_argument('--disable-dev-shm-usage')
opts.add_argument('--window-size=1400,900')

driver = webdriver.Chrome(options=opts)
try:
    driver.get('http://localhost:3000')
    time.sleep(1)
    # Ensure IDE section is visible
    driver.execute_script("document.querySelector('[data-target=ide]')?.click();")
    time.sleep(1)
    prompt = driver.find_element(By.ID, 'aiPrompt')
    driver.execute_script("arguments[0].value = 'crie uma função soma em python'; arguments[0].dispatchEvent(new Event('input'))", prompt)
    time.sleep(0.3)
    run_btn = driver.find_element(By.ID, 'aiPromptRun')
    driver.execute_script("arguments[0].click()", run_btn)
    time.sleep(1)
    out = driver.find_element(By.ID, 'output').text
    print('OUTPUT IMEDIATO:\n', out[:1000])
    # wait a bit
    time.sleep(2)
    out2 = driver.find_element(By.ID, 'output').text
    print('\nOUTPUT APOS 2s:\n', out2[:2000])
finally:
    driver.quit()
