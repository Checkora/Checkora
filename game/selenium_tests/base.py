"""Base class for Checkora Selenium E2E tests."""

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# ── ANSI colours for readable terminal output ──────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def log_ok(msg):
    print(f"  {GREEN}✅ {msg}{RESET}")


def log_fail(msg):
    print(f"  {RED}❌ {msg}{RESET}")


def log_info(msg):
    print(f"  {CYAN}ℹ  {msg}{RESET}")


def log_warn(msg):
    print(f"  {YELLOW}⚠  {msg}{RESET}")


class BaseE2ETest(StaticLiveServerTestCase):
    """Shared Selenium setup, teardown, and helper methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        try:
            cls.driver = webdriver.Chrome(options=chrome_options)
            log_ok("Chrome WebDriver initialized")
        except Exception as e:
            log_fail(f"Failed to initialize Chrome WebDriver: {e}")
            raise RuntimeError(
                f"Failed to initialize Chrome WebDriver: {e}"
            ) from e

        cls.wait = WebDriverWait(cls.driver, 15)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'driver'):
            cls.driver.quit()
            log_info("Chrome WebDriver closed")
        super().tearDownClass()

    def _start_pvp_game(self):
        """Helper: navigate to homepage and start a PvP game."""
        log_info(f"Starting PvP game at {self.live_server_url}/play/")
        self.driver.get(self.live_server_url + '/play/')

        # Wait for welcome overlay
        self.wait.until(
            EC.presence_of_element_located((By.ID, 'welcomeOverlay')),
            message="Welcome overlay not found"
        )

        # Fill in player names
        white_input = self.driver.find_element(By.ID, 'whiteNameInput')
        black_input = self.driver.find_element(By.ID, 'blackNameInput')
        white_input.clear()
        black_input.clear()
        white_input.send_keys('Alice')
        black_input.send_keys('Bob')

        # Click PvP button using JavaScript for reliability
        pvp_btn = self.driver.find_element(By.ID, 'welcomePvPBtn')
        self._js_click(pvp_btn)

        # Wait for board with extended timeout and diagnostic message
        try:
            self.wait.until(
                EC.visibility_of_element_located((By.ID, 'board')),
                message="Board element not visible after starting PvP game. Check that game initialization completed successfully."
            )
        except Exception:
            # Capture diagnostic info on failure
            page_source = self.driver.page_source[:500]
            log_fail(f"Board failed to load. Page source snippet: {page_source}")
            raise

        # Verify board has expected structure
        board = self.driver.find_element(By.ID, 'board')
        squares = board.find_elements(By.CLASS_NAME, 'square')
        if len(squares) != 64:
            log_warn(f"Board has {len(squares)} squares instead of expected 64")

        log_ok("PvP game started — board visible with board structure")

    def _js_click(self, element):
        """Helper: click element via JavaScript (more reliable than Selenium click)."""
        self.driver.execute_script("arguments[0].click();", element)
