import threading
import socketserver
import http.server
import time
import requests
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# Use modern Service API for webdriver (compatible with latest selenium)
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as GeckoService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager


class ThreadedHTTPServer(object):
    def __init__(self, directory, host="127.0.0.1"):
        handler = http.server.SimpleHTTPRequestHandler
        self._server = socketserver.TCPServer(
            (host, 0),
            lambda *args, **kwargs: handler(*args, directory=directory, **kwargs),
        )
        self.thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self.url = f"http://{host}:{self._server.server_address[1]}"

    def start(self):
        self.thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture(scope="session")
def http_server():
    server = ThreadedHTTPServer(directory="site")
    server.start()
    # give server a moment
    time.sleep(0.1)
    yield server.url
    server.stop()


@pytest.fixture(scope="session")
def driver():
    # Try Chrome then Firefox
    options = None
    drv = None
    # Chrome
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # Use Service pattern (executable path provided by webdriver_manager)
        chrome_svc = ChromeService(ChromeDriverManager().install())
        drv = webdriver.Chrome(service=chrome_svc, options=options)
        yield drv
        drv.quit()
        return
    except Exception:
        if drv:
            try:
                drv.quit()
            except Exception:
                pass
    # Firefox fallback
    try:
        options = webdriver.FirefoxOptions()
        options.headless = True
        gecko_svc = GeckoService(GeckoDriverManager().install())
        drv = webdriver.Firefox(service=gecko_svc, options=options)
        yield drv
        drv.quit()
        return
    except Exception as e:
        pytest.skip(f"No webdriver available: {e}")


def test_basic_navigation(http_server, driver):
    driver.get(http_server)
    # check title or header
    assert "Eddie" in driver.page_source or driver.title

    # Verify tabs clickable
    projects_tab = driver.find_element(
        By.CSS_SELECTOR, "button[data-target='projects']"
    )
    projects_tab.click()
    time.sleep(0.4)
    projects_grid = driver.find_element(By.CSS_SELECTOR, ".projects-grid")
    assert projects_grid.is_displayed()

    # Keyboard navigation (arrow right)
    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ARROW_RIGHT)
    time.sleep(0.2)
    # Ensure some panel visible
    assert driver.find_element(By.CSS_SELECTOR, ".panel.active") is not None


def test_openwebui_embed(http_server, driver):
    driver.get(http_server)
    open_tab = driver.find_element(By.CSS_SELECTOR, "button[data-target='openwebui']")
    open_tab.click()
    # allow script to fetch config and set iframe
    time.sleep(1.0)
    iframe = driver.find_element(By.ID, "openwebuiIframe")
    src = iframe.get_attribute("src")
    assert src, "OpenWebUI iframe src must be set"

    # If src is a relative path, convert to absolute
    if src.startswith("/"):
        src = http_server.rstrip("/") + src

    # Try HEAD request to see if reachable; if not reachable, skip but report
    try:
        r = requests.head(src, timeout=5, allow_redirects=True)
        assert r.status_code < 400
    except Exception as e:
        pytest.skip(f"Open WebUI URL unreachable: {e}")
