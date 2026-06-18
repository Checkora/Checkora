from django.contrib.auth import get_user_model
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from .base import BaseE2ETest, log_ok, log_info


class AdminHealthDashboardTests(BaseE2ETest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        User = get_user_model()

        cls.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@test.com",
            password="admin123"
        )

    def test_health_dashboard_visible(self):

        log_info("Testing admin dashboard...")

        self.driver.get(
            self.live_server_url + "/admin/login/"
        )

        self.driver.find_element(
            By.ID,
            "id_username"
        ).send_keys("admin")

        self.driver.find_element(
            By.ID,
            "id_password"
        ).send_keys("admin123")

        self.driver.find_element(
            By.XPATH,
            '//input[@type="submit"]'
        ).click()

        self.wait.until(
            EC.text_to_be_present_in_element(
                (By.TAG_NAME, "body"),
                "System Health Dashboard"
            )
        )
                
        page = self.driver.page_source

        self.assertIn(
            "System Health Dashboard",
            page
        )

        self.assertIn(
            "Database",
            page
        )

        self.assertIn(
            "Puzzle System",
            page
        )

        self.assertIn(
            "Achievement System",
            page
        )

        self.assertIn(
            "Lesson System",
            page
        )

        self.assertIn(
            "Opening Trainer",
            page
        )
        
        self.assertIn(
            "Total Users",
            page
        )

        self.assertIn(
            "Total Puzzles",
            page
        )

        log_ok("Health dashboard visible")
