"""UI tests — overlay, board render, timers, buttons, theme."""

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseE2ETest, log_ok, log_fail, log_info


class UITest(BaseE2ETest):

    # ───────────────────────────────────────────────────────────────
    # Test 1: Welcome Overlay
    # ───────────────────────────────────────────────────────────────
    def test_01_welcome_overlay_loads(self):
        """Welcome overlay loads with name inputs and mode buttons."""
        log_info("Testing welcome overlay...")
        self.driver.get(self.live_server_url + '/play/')

        welcome_overlay = self.wait.until(
            EC.presence_of_element_located((By.ID, 'welcomeOverlay')),
            message="Welcome overlay not found"
        )
        self.assertTrue(welcome_overlay.is_displayed())
        log_ok("Welcome overlay visible")

        white_name_input = self.driver.find_element(By.ID, 'whiteNameInput')
        black_name_input = self.driver.find_element(By.ID, 'blackNameInput')
        self.assertIsNotNone(white_name_input)
        self.assertIsNotNone(black_name_input)
        log_ok("Name inputs found")

        pvp_btn = self.driver.find_element(By.ID, 'welcomePvPBtn')
        ai_btn = self.driver.find_element(By.ID, 'welcomeAIBtn')
        self.assertIsNotNone(pvp_btn)
        self.assertIsNotNone(ai_btn)
        log_ok("PvP and AI buttons found")

    # ───────────────────────────────────────────────────────────────
    # Test 2: Start PvP Game
    # ───────────────────────────────────────────────────────────────
    def test_02_can_start_pvp_game(self):
        """Entering names and clicking PvP starts a game."""
        log_info("Testing PvP game start...")
        self._start_pvp_game()

        mode_badge = self.driver.find_element(By.ID, 'modeBadge')
        self.assertIn('PVP', mode_badge.text.upper())
        log_ok(f"Mode badge shows: {mode_badge.text}")

    # ───────────────────────────────────────────────────────────────
    # Test 3: Board Renders with 64 Squares and Pieces
    # ───────────────────────────────────────────────────────────────
    def test_03_board_renders_with_pieces(self):
        """Board has 64 squares and initial pieces rendered."""
        log_info("Testing board render...")
        self._start_pvp_game()

        board = self.wait.until(
            EC.presence_of_element_located((By.ID, 'board')),
            message="Board not found"
        )

        squares = board.find_elements(By.CLASS_NAME, 'square')
        self.assertEqual(len(squares), 64, f"Expected 64 squares, got {len(squares)}")
        log_ok("64 squares found")

        pieces = board.find_elements(By.TAG_NAME, 'img')
        self.assertGreater(len(pieces), 0, "No pieces found on board")
        log_ok(f"{len(pieces)} piece images found")

    # ───────────────────────────────────────────────────────────────
    # Test 4: Timers Visible
    # ───────────────────────────────────────────────────────────────
    def test_04_game_timers_visible(self):
        """White and black timers are displayed after game starts."""
        log_info("Testing game timers...")
        self._start_pvp_game()

        white_time = self.wait.until(
            EC.presence_of_element_located((By.ID, 'whiteTime')),
            message="White timer not found"
        )
        black_time = self.driver.find_element(By.ID, 'blackTime')

        self.assertTrue(white_time.is_displayed())
        self.assertTrue(black_time.is_displayed())
        log_ok(f"White timer: {white_time.text} | Black timer: {black_time.text}")

    # ───────────────────────────────────────────────────────────────
    # Test 5: Login Page
    # ───────────────────────────────────────────────────────────────
    def test_05_login_page_accessible(self):
        """Login page loads with username and password fields."""
        log_info("Testing login page...")
        self.driver.get(self.live_server_url + '/login/')

        login_form = self.wait.until(
            EC.presence_of_element_located((By.NAME, 'username')),
            message="Login username field not found"
        )
        self.assertIsNotNone(login_form)

        password_field = self.driver.find_element(By.NAME, 'password')
        self.assertIsNotNone(password_field)
        log_ok("Login form fields found")

    # ───────────────────────────────────────────────────────────────
    # Test 6: Register Page
    # ───────────────────────────────────────────────────────────────
    def test_06_register_page_accessible(self):
        """Register page loads with a form."""
        log_info("Testing register page...")
        self.driver.get(self.live_server_url + '/register/')

        register_form = self.wait.until(
            EC.presence_of_element_located((By.NAME, 'username')),
            message="Register form not found"
        )
        self.assertIsNotNone(register_form)
        log_ok("Register form found")

    # ───────────────────────────────────────────────────────────────
    # Test 7: Pause Button
    # ───────────────────────────────────────────────────────────────
    def test_07_pause_button_exists(self):
        """Pause button is visible and clickable after game starts."""
        log_info("Testing pause button...")
        self._start_pvp_game()

        pause_btn = self.wait.until(
            EC.element_to_be_clickable((By.ID, 'pauseBtn')),
            message="Pause button not found or not clickable"
        )
        self.assertTrue(pause_btn.is_displayed())
        log_ok(f"Pause button found: '{pause_btn.text}'")

    # ───────────────────────────────────────────────────────────────
    # Test 8: Flip Board Button
    # ───────────────────────────────────────────────────────────────
    def test_08_flip_board_button_exists(self):
        """Flip board button is visible and clickable."""
        log_info("Testing flip board button...")
        self._start_pvp_game()

        flip_btn = self.wait.until(
            EC.element_to_be_clickable((By.ID, 'flipBtn')),
            message="Flip button not found or not clickable"
        )
        self.assertTrue(flip_btn.is_displayed())
        log_ok(f"Flip button found: '{flip_btn.text}'")

    # ───────────────────────────────────────────────────────────────
    # Test 9: Theme Switcher
    # ───────────────────────────────────────────────────────────────
    def test_09_theme_switcher_buttons_exist(self):
        """4 theme buttons (classic, dark, green, blue) are present."""
        log_info("Testing theme switcher...")
        self._start_pvp_game()

        theme_btns = self.wait.until(
            lambda d: d.find_elements(By.CLASS_NAME, 'theme-btn'),
            message="Theme buttons not found"
        )
        self.assertEqual(len(theme_btns), 4, f"Expected 4 theme buttons, got {len(theme_btns)}")
        log_ok(f"{len(theme_btns)} theme buttons found")
