from django.test import TestCase
from game.progression import calculate_level, LEVEL_THRESHOLDS

class ProgressionTests(TestCase):
    def test_calculate_level_standard_values(self):
        """Test that standard XP values return the correct level based on thresholds."""
        self.assertEqual(calculate_level(0), 1)
        self.assertEqual(calculate_level(50), 1)
        self.assertEqual(calculate_level(100), 2)
        self.assertEqual(calculate_level(150), 2)
        self.assertEqual(calculate_level(250), 3)
        self.assertEqual(calculate_level(1000), 5)
        self.assertEqual(calculate_level(1500), 6)

    def test_calculate_level_exact_boundaries(self):
        """Test the exact inclusive threshold boundaries."""
        for level, threshold in LEVEL_THRESHOLDS.items():
            self.assertEqual(calculate_level(threshold), level)

    def test_calculate_level_max_cap(self):
        """Test XP values exceeding the highest threshold correctly cap at max level."""
        max_level = max(LEVEL_THRESHOLDS.keys())
        highest_threshold = max(LEVEL_THRESHOLDS.values())
        
        self.assertEqual(calculate_level(highest_threshold), max_level)
        self.assertEqual(calculate_level(highest_threshold + 5000), max_level)
        self.assertEqual(calculate_level(999999), max_level)

    def test_calculate_level_negative_xp(self):
        """Test that passing a negative XP value raises a ValueError."""
        with self.assertRaises(ValueError) as context:
            calculate_level(-1)
        self.assertEqual(str(context.exception), "xp must be non-negative, got -1")
        
        with self.assertRaises(ValueError):
            calculate_level(-1000)
