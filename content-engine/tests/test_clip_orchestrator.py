import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from core.clip_orchestrator import PyPongAIClipOrchestrator

@pytest.fixture
def mock_config():
    return {
        "game_path": "/fake/path",
        "output_dir": "test_clips",
        "match_duration_target": 5,
        "ffmpeg": {
            "method": "gdigrab",
            "fps": 30
        }
    }

@patch("core.clip_orchestrator.PyPongAIController")
@patch("core.clip_orchestrator.ScreenRecorder")
def test_record_match(mock_recorder, mock_controller, mock_config, tmp_path):
    # Setup mocks
    mock_config["output_dir"] = str(tmp_path)
    mock_ctrl_inst = mock_controller.return_value
    mock_ctrl_inst.launch_game.return_value = True
    
    mock_rec_inst = mock_recorder.return_value
    fake_mp4 = tmp_path / "clip_gen_0_test.mp4"
    mock_rec_inst.start_recording.return_value = fake_mp4
    
    # Run subject
    orch = PyPongAIClipOrchestrator(mock_config)
    res = orch.record_match("gen_0", duration_s=1)
    
    # Assertions
    assert "error" not in res
    assert res["model_name"] == "gen_0"
    assert res["duration"] == 1
    
    # Assert json was created
    expected_meta = fake_mp4.with_suffix(".json")
    assert expected_meta.exists()
    
    # Check Controller Calls
    mock_ctrl_inst.launch_game.assert_called_once()
    mock_ctrl_inst.click_menu_button.assert_any_call("play_button")
    mock_ctrl_inst.click_menu_button.assert_any_call("start_button")
    mock_ctrl_inst.close_game.assert_called_once()

    # Check Recorder Calls
    mock_rec_inst.start_recording.assert_called_once_with("gen_0")
    mock_rec_inst.stop_recording.assert_called_once()
