import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.prompt_builder import build_variant_prompts

class TestPromptBuilder(unittest.TestCase):
    def test_build_variant_prompts_returns_n_items(self):
        prompts = build_variant_prompts("Cookie Clicker", "prestige", "reset", n=3)
        self.assertEqual(len(prompts), 3)

    def test_build_variant_prompts_first_is_base(self):
        prompts = build_variant_prompts("Cookie Clicker", "prestige", "reset", n=2)
        self.assertIn("Cookie Clicker", prompts[0])
        self.assertNotIn("close-up detail", prompts[0])

    def test_variant_modifiers_cycle_by_index(self):
        # We know the first modifier is "close-up detail"
        prompts = build_variant_prompts("Cookie Clicker", "prestige", "reset", n=2)
        self.assertIn("close-up detail", prompts[1])

if __name__ == "__main__":
    unittest.main()
