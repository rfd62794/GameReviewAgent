import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.reference_manager import get_reference, acquire_reference

class TestReferenceManager(unittest.TestCase):
    @patch("core.reference_manager.get_connection")
    def test_get_reference_with_mechanic_queries_mechanic_specific_first(self, mock_conn_fn):
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn
        
        # 1. Mock mechanic match in DB
        mock_conn.execute.return_value.fetchone.return_value = {"reference_image_path": "fake/path/mech.png"}
        
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("pathlib.Path.read_bytes") as mock_read:
                mock_read.return_value = b"bytes"
                
                res = get_reference("Cookie Clicker", "prestige_reset")
                self.assertEqual(res, b"bytes")
                
                # Verify first query used mechanic
                first_query = mock_conn.execute.call_args_list[0][0][0]
                self.assertIn("mechanic = ?", first_query)

    @patch("core.reference_manager.acquire_reference")
    @patch("core.reference_manager.get_connection")
    def test_get_reference_falls_back_to_game_level(self, mock_conn_fn, mock_acquire):
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn
        
        # 1. Mock No Mechanic Match, then General Match
        mock_conn.execute.return_value.fetchone.side_effect = [
            None, # Mechanic specific
            {"reference_image_path": "fake/path/general.png"} # General
        ]
        
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = True
            with patch("pathlib.Path.read_bytes") as mock_read:
                mock_read.return_value = b"general_bytes"
                
                res = get_reference("Cookie Clicker", "prestige_reset")
                self.assertEqual(res, b"general_bytes")
                
                # Verify general fallback query
                queries = [call[0][0] for call in mock_conn.execute.call_args_list]
                self.assertTrue(any("mechanic IS NULL" in q or "mechanic = 'N/A'" in q for q in queries))

if __name__ == "__main__":
    unittest.main()
