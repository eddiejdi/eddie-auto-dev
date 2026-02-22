import pytest

try:
    from selenium import webdriver
except ImportError:
    webdriver = None


@pytest.fixture
def driver():
    if webdriver is None:
        pytest.skip("selenium not installed")
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        drv = webdriver.Chrome(options=options)
    except Exception as e:
        pytest.skip(f"Cannot start Chrome driver: {e}")
        return
    yield drv
    try:
        drv.quit()
    except Exception:
        pass
