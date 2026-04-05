import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.assembler import preprocess_segment, _format_timestamp

class TestAssembler(unittest.TestCase):
    def test_format_timestamp(self):
        self.assertEqual(_format_timestamp(61.5), "00:01:01,500")
        self.assertEqual(_format_timestamp(3661.001), "01:01:01,001")

    @patch("subprocess.run")
    @patch("shutil.move")
    def test_ken_burns_cycling_calculates_correct_intervals(self, mock_move, mock_run):
        segment = {
            "segment_index": 0,
            "estimated_duration_s": 25,
            "selected_asset": "img.png",
            "image_paths": json.dumps(["img1.png", "img2.png"]),
            "visual_type": "image"
        }
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            config = {
                "image_cycling_enabled": True,
                "image_cycling_interval_s": 10
            }
            
            # 25s duration / 10s interval = 3 intervals (10, 10, 5)
            preprocess_segment(segment, temp_dir, config)
            
            # Verify subprocess.run was called for each interval (3 times) + 1 for concat
            # Total calls = 4
            self.assertEqual(mock_run.call_count, 4)
        
    @patch("subprocess.run")
    @patch("shutil.move")
    def test_cycling_wraps_images(self, mock_move, mock_run):
        segment = {
            "segment_index": 1,
            "estimated_duration_s": 30,
            "selected_asset": "img.png",
            "image_paths": json.dumps(["only_one.png"]),
            "visual_type": "image"
        }
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            config = {
                "image_cycling_enabled": True,
                "image_cycling_interval_s": 10
            }
            
            # 30s duration / 10s interval = 3 intervals
            # But only 1 unique image provided. It should wrap.
            preprocess_segment(segment, temp_dir, config)
            
            # Check that the 3 interval commands all used "only_one.png"
            calls = mock_run.call_args_list
            # First 3 calls are the interval generations
            for i in range(3):
                cmd = calls[i][0][0]
                self.assertIn("only_one.png", cmd)

if __name__ == "__main__":
    unittest.main()
