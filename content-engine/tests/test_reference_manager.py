import unittest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.reference_manager import get_reference

class TestReferenceManager(unittest.TestCase):
    @patch("core.reference_manager.get_connection")
    @patch("core.reference_manager.Path")
    def test_get_reference_with_mechanic_queries_mechanic_specific_first(self, mock_path_class, mock_conn_fn):
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn
        
        # 1. Mock mechanic match in DB
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"reference_image_path": "fake/path/mech.png"}
        
        # Mock Path behaviors
        mock_instance = mock_path_class.return_value
        mock_instance.exists.return_value = True
        mock_instance.read_bytes.return_value = b"bytes"
        
        res = get_reference("Cookie Clicker", "prestige_reset")
        self.assertEqual(res, b"bytes")
        
        # Verify first query used mechanic
        first_query = mock_conn.execute.call_args_list[0][0][0]
        self.assertIn("mechanic = ?", first_query)

    @patch("core.reference_manager.get_connection")
    @patch("core.reference_manager.acquire_reference")
    @patch("core.reference_manager.Path")
    def test_get_reference_falls_back_to_game_level(self, mock_path_class, mock_acquire, mock_conn_fn):
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn
        
        # 1. Mock No Mechanic Match in DB, then General Match in DB
        mock_cursor = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [
            None, # Mechanic specific DB check fails
            {"reference_image_path": "fake/path/general.png"} # General DB check hits
        ]
        
        # 2. Mock mechanic acquisition failing (to trigger fallback)
        mock_acquire.return_value = None
        
        # Mock Path behaviors for general match
        mock_instance = mock_path_class.return_value
        mock_instance.exists.return_value = True
        mock_instance.read_bytes.return_value = b"general_bytes"
        
        res = get_reference("Cookie Clicker", "prestige_reset")
        self.assertEqual(res, b"general_bytes")
        
        # Verify general fallback query was made correctly
        queries = [call[0][0] for call in mock_conn.execute.call_args_list]
        self.assertTrue(any("mechanic IS NULL" in q or "mechanic = 'N/A'" in q for q in queries))

if __name__ == "__main__":
    unittest.main()
