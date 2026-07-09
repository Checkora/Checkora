import importlib
import os
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase


class SettingsTests(SimpleTestCase):
    def test_missing_secret_key_uses_dev_fallback_when_debug_enabled(self):
        with patch.dict(os.environ, {"DEBUG": "True"}, clear=False):
            os.environ.pop("SECRET_KEY", None)
            settings_module = importlib.import_module("core.settings")
            reloaded_module = importlib.reload(settings_module)

            self.assertEqual(reloaded_module.SECRET_KEY, "dev-secret-key-for-local-testing")

    def test_missing_secret_key_raises_when_debug_disabled(self):
        with patch.dict(os.environ, {"DEBUG": "False"}, clear=False):
            os.environ.pop("SECRET_KEY", None)
            settings_module = importlib.import_module("core.settings")

            with self.assertRaises(ImproperlyConfigured):
                importlib.reload(settings_module)
