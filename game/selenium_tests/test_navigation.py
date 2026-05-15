"""Navigation tests — page routing, overlays, mode switching."""

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseE2ETest, log_ok, log_info


class NavigationTest(BaseE2ETest):

    # ───────────────────────────────────────────────────────────────
    # Test 1: Homepage (Landing Page) Loads
    # ───────────────────────────────────────────────────────────────
    def test_01_homepage_loads(self):
        """Homepage returns 200 and renders the landing page."""
        log_info("Testing homepage loads...")
        self.driver.get(self.live_server_url + '/')

        self.wait.until(
            EC.presence_of_element_located((By.TAG_NAME, 'body')),
            message="Homepage did not load"
        )
        self.assertEqual(
            self.driver.current_url.rstrip('/'),
            self.live_server_url.rstrip('/'),
            "Homepage URL does not match"
        )
        log_ok(f"Homepage loaded — title: '{self.driver.title}'")

    # ───────────────────────────────────────────────────────────────
    # Test 2: Play Page Welcome Overlay
    # ───────────────────────────────────────────────────────────────
    def test_02_welcome_overlay_loads(self):
        """Welcome overlay has name inputs and mode buttons."""
        log_info("Testing welcome overlay elements...")
        self.driver.get(self.live_server_url + '/play/')

        welcome_overlay = self.wait.until(
            EC.presence_of_element_located((By.ID, 'welcomeOverlay')),
            message="Welcome overlay not found"
        )
        self.assertTrue(welcome_overlay.is_displayed())
        log_ok("Welcome overlay visible")

        # Name inputs
        white_input = self.driver.find_element(By.ID, 'whiteNameInput')
        black_input = self.driver.find_element(By.ID, 'blackNameInput')
        self.assertIsNotNone(white_input)
        self.assertIsNotNone(black_input)
        log_ok("Name inputs present")

        # Mode buttons
        pvp_btn = self.driver.find_element(By.ID, 'welcomePvPBtn')
        ai_btn = self.driver.find_element(By.ID, 'welcomeAIBtn')
        self.assertIsNotNone(pvp_btn)
        self.assertIsNotNone(ai_btn)
        log_ok("PvP and AI buttons present")

    # ───────────────────────────────────────────────────────────────
    # Test 3: PvP Mode Starts and Mode Badge Updates
    # ───────────────────────────────────────────────────────────────
    def test_03_pvp_mode_starts(self):
        """Entering names and clicking PvP dismisses overlay and shows PVP badge."""
        log_info("Testing PvP mode start...")
        self._start_pvp_game()

        # Overlay should be gone
        welcome_overlay = self.driver.find_element(By.ID, 'welcomeOverlay')
        self.assertFalse(
            'active' in welcome_overlay.get_attribute('class'),
            "Welcome overlay still active after starting game"
        )
        log_ok("Welcome overlay dismissed")

        # Mode badge should show PVP
        mode_badge = self.driver.find_element(By.ID, 'modeBadge')
        self.assertIn('PVP', mode_badge.text.upper())
        log_ok(f"Mode badge: '{mode_badge.text}'")

    # ───────────────────────────────────────────────────────────────
    # Test 4: AI Mode Button Shows PvE Options
    # ───────────────────────────────────────────────────────────────
    def test_04_ai_mode_shows_pve_options(self):
        """Clicking Play vs AI reveals difficulty and color selection."""
        log_info("Testing AI mode options...")
        self.driver.get(self.live_server_url + '/play/')

        self.wait.until(
            EC.presence_of_element_located((By.ID, 'welcomeOverlay'))
        )

        ai_btn = self.driver.find_element(By.ID, 'welcomeAIBtn')
        ai_btn.click()

        # PvE options should be visible
        pve_options = self.wait.until(
            EC.visibility_of_element_located((By.ID, 'pveOptions')),
            message="PvE options not shown after clicking AI button"
        )
        self.assertTrue(pve_options.is_displayed())
        log_ok("PvE options panel visible")

        # Difficulty select should be present
        difficulty = self.driver.find_element(By.ID, 'welcomeDifficultySelect')
        self.assertIsNotNone(difficulty)
        log_ok("Difficulty selector present")

        # Color choice buttons should be present
        color_btns = self.driver.find_elements(By.CLASS_NAME, 'color-choice')
        self.assertEqual(
            len(color_btns), 2,
            f"Expected 2 color buttons, got {len(color_btns)}"
        )
        log_ok("White/Black color buttons present")

    # ───────────────────────────────────────────────────────────────
    # Test 5: Back Button Returns to Mode Selection
    # ───────────────────────────────────────────────────────────────
    def test_05_back_button_returns_to_mode_selection(self):
        """Back button in PvE options returns to mode selection screen."""
        log_info("Testing back button...")
        self.driver.get(self.live_server_url + '/play/')

        self.wait.until(
            EC.presence_of_element_located((By.ID, 'welcomeOverlay'))
        )

        # Go to AI options
        self.driver.find_element(By.ID, 'welcomeAIBtn').click()

        self.wait.until(
            EC.visibility_of_element_located((By.ID, 'pveOptions'))
        )

        # Click back
        back_btn = self.driver.find_element(By.ID, 'backToModes')
        back_btn.click()

        # Mode selection should be visible again
        mode_selection = self.wait.until(
            EC.visibility_of_element_located((By.ID, 'modeSelection')),
            message="Mode selection not visible after clicking back"
        )
        self.assertTrue(mode_selection.is_displayed())
        log_ok("Mode selection restored after back button")

    # ───────────────────────────────────────────────────────────────
    # Test 6: Login Page Route
    # ───────────────────────────────────────────────────────────────
    def test_06_login_page_route(self):
        """Navigating to /login/ loads the login page."""
        log_info("Testing /login/ route...")
        self.driver.get(self.live_server_url + '/login/')

        self.wait.until(
            EC.presence_of_element_located((By.NAME, 'username')),
            message="/login/ did not load correctly"
        )
        self.assertEqual(
            self.driver.current_url,
            self.live_server_url + '/login/'
        )
        log_ok(f"Login page loaded at {self.driver.current_url}")

    # ───────────────────────────────────────────────────────────────
    # Test 7: Register Page Route
    # ───────────────────────────────────────────────────────────────
    def test_07_register_page_route(self):
        """Navigating to /register/ loads the register page."""
        log_info("Testing /register/ route...")
        self.driver.get(self.live_server_url + '/register/')

        self.wait.until(
            EC.presence_of_element_located((By.NAME, 'username')),
            message="/register/ did not load correctly"
        )
        self.assertEqual(
            self.driver.current_url,
            self.live_server_url + '/register/'
        )
        log_ok(f"Register page loaded at {self.driver.current_url}")

    # ───────────────────────────────────────────────────────────────
    # Test 8: Rules Page Route
    # ───────────────────────────────────────────────────────────────
    def test_08_rules_page_route(self):
        """Navigating to /rules/ loads the rules page."""
        log_info("Testing /rules/ route...")
        self.driver.get(self.live_server_url + '/rules/')

        # Wait for body to load
        self.wait.until(
            EC.presence_of_element_located((By.TAG_NAME, 'body')),
            message="/rules/ did not load"
        )
        self.assertEqual(
            self.driver.current_url,
            self.live_server_url + '/rules/'
        )
        log_ok(f"Rules page loaded at {self.driver.current_url}")

    # ───────────────────────────────────────────────────────────────
    # Test 9: Stats Page Route
    # ───────────────────────────────────────────────────────────────
    def test_09_stats_page_route(self):
        """Navigating to /stats/ redirects unauthenticated user to login."""
        log_info("Testing /stats/ route...")
        self.driver.get(self.live_server_url + '/stats/')

        self.wait.until(
            EC.presence_of_element_located((By.TAG_NAME, 'body')),
            message="/stats/ did not load"
        )
        # Stats requires authentication — should redirect to login
        self.assertIn(
            '/login/',
            self.driver.current_url,
            "Expected redirect to login page for unauthenticated user"
        )
        log_ok(f"Stats redirected to login: {self.driver.current_url}")

    # ───────────────────────────────────────────────────────────────
    # Test 10: Header Auth Buttons for Unauthenticated User
    # ───────────────────────────────────────────────────────────────
    def test_10_header_shows_signin_register_when_logged_out(self):
        """Header shows Sign In and Register buttons when not logged in."""
        log_info("Testing header auth buttons...")
        self._start_pvp_game()

        # Sign In button should be present
        signin_btn = self.wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'btn-signin')),
            message="Sign In button not found in header"
        )
        self.assertTrue(signin_btn.is_displayed())
        log_ok(f"Sign In button found: '{signin_btn.text}'")

        # Register button should be present
        register_btn = self.driver.find_element(By.CLASS_NAME, 'btn-register')
        self.assertTrue(register_btn.is_displayed())
        log_ok(f"Register button found: '{register_btn.text}'")

    # ───────────────────────────────────────────────────────────────
    # Test 11: Name Validation Error Shows on Empty Submit
    # ───────────────────────────────────────────────────────────────
    def test_11_name_validation_error_on_empty_submit(self):
        """Clicking PvP without entering names shows validation error."""
        log_info("Testing name validation...")
        self.driver.get(self.live_server_url + '/play/')

        self.wait.until(
            EC.presence_of_element_located((By.ID, 'welcomeOverlay'))
        )

        # Click PvP without entering names
        pvp_btn = self.driver.find_element(By.ID, 'welcomePvPBtn')
        pvp_btn.click()

        # Error div should be visible
        error_div = self.wait.until(
            EC.visibility_of_element_located((By.ID, 'nameError')),
            message="Validation error not shown after empty name submit"
        )
        self.assertTrue(error_div.is_displayed())
        log_ok(f"Validation error shown: '{error_div.text}'")
