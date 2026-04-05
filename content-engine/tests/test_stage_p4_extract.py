import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import get_connection
import stage_p4_extract

class TestStageP4Extract(unittest.TestCase):
    def setUp(self):
        self.conn = get_connection()
        self.conn.execute("DELETE FROM asset_briefs WHERE script_id = 999")
        self.conn.execute("DELETE FROM scripts WHERE id = 999")
        self.conn.execute(
            "INSERT INTO scripts (id, topic_id, hook_short_script, mid_form_body, word_count_hook, word_count_body, estimated_duration_s) "
            "VALUES (999, 1, 'hook', 'body', 1, 1, 1)"
        )
        self.conn.execute(
            "INSERT INTO asset_briefs (script_id, segment_index, segment_text, estimated_duration_s, visual_type, search_query) "
            "VALUES (999, 0, 'Test segment text', 5, 'stock_clip', '')"
        )
        self.conn.commit()
        stage_p4_extract.SCRIPT_ID = 999

    def tearDown(self):
        self.conn.execute("DELETE FROM asset_briefs WHERE script_id = 999")
        self.conn.execute("DELETE FROM scripts WHERE id = 999")
        self.conn.commit()
        self.conn.close()

    @patch("stage_p4_extract.extract_mechanic")
    def test_extract_writes_game_title_to_db(self, mock_extract):
        mock_extract.return_value = {
            "games": ["TestGame"],
            "mechanic": "test_mech",
            "moment": "test_moment",
            "search_queries": ["query1"]
        }
        
        stage_p4_extract.main()
        
        row = self.conn.execute("SELECT * FROM asset_briefs WHERE script_id = 999").fetchone()
        assert row["game_title"] == "TestGame"
        assert row["mechanic"] == "test_mech"
        assert row["moment"] == "test_moment"

    @patch("stage_p4_extract.extract_mechanic")
    def test_extract_handles_null_game_gracefully(self, mock_extract):
        mock_extract.return_value = {
            "games": [],  # Null game
            "mechanic": "test_mech",
            "moment": "test_moment",
            "search_queries": []
        }
        
        stage_p4_extract.main()
        
        row = self.conn.execute("SELECT * FROM asset_briefs WHERE script_id = 999").fetchone()
        assert row["game_title"] is None
        assert row["mechanic"] == "test_mech"

    @patch("stage_p4_extract.extract_mechanic")
    def test_extract_does_not_overwrite_already_extracted_segments(self, mock_extract):
        # Pre-set mechanic
        self.conn.execute("UPDATE asset_briefs SET mechanic = 'existing' WHERE script_id = 999")
        self.conn.commit()
        
        stage_p4_extract.main()
        
        # Mock extract should NEVER be called
        mock_extract.assert_not_called()
        
        row = self.conn.execute("SELECT * FROM asset_briefs WHERE script_id = 999").fetchone()
        assert row["mechanic"] == "existing"

if __name__ == "__main__":
    unittest.main()
