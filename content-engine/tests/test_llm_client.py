import sys
import json
import base64
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.llm_client import OpenRouterLLMAdapter, LLMError

class TestLLMClient(unittest.TestCase):
    def setUp(self):
        self.adapter = OpenRouterLLMAdapter(api_key="sk-test")

    @patch("requests.post")
    def test_standard_generate_payload(self, mock_post):
        # Mock successful response
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "{\"test\": true}"}}],
            "usage": {"total_tokens": 10}
        }
        
        self.adapter.generate("Hello")
        
        # Verify payload DOES NOT have modalities or image_config
        payload = mock_post.call_args.kwargs["json"]
        self.assertNotIn("modalities", payload)
        self.assertNotIn("image_config", payload)
        self.assertEqual(payload["model"], self.adapter.model)

    @patch("requests.post")
    def test_generate_image_payload(self, mock_post):
        # Mock successful base64 response
        fake_base64 = base64.b64encode(b"fake_png_bytes").decode()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{
                "message": {
                    "images": [{
                        "image_url": {"url": f"data:image/png;base64,{fake_base64}"}
                    }]
                }
            }]
        }
        
        res = self.adapter.generate_image("A cat", aspect_ratio="9:16", image_size="1K")
        
        # Verify payload DOES have modalities and image_config
        payload = mock_post.call_args.kwargs["json"]
        self.assertIn("modalities", payload)
        self.assertEqual(payload["modalities"], ["image", "text"])
        self.assertIn("image_config", payload)
        self.assertEqual(payload["image_config"]["aspect_ratio"], "9:16")
        
        # Verify bytes
        self.assertEqual(res, b"fake_png_bytes")

    def test_payload_side_by_side(self):
        """Manual verification for the user of payload differences."""
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": "text", "images": []}}]
            }
            
            # 1. Text Call
            self.adapter.generate("text prompt")
            text_payload = mock_post.call_args.kwargs["json"]
            
            # 2. Image Call
            self.adapter.generate_image("image prompt")
            image_payload = mock_post.call_args.kwargs["json"]
            
            print("\n--- PAYLOAD COMPARISON ---")
            print(f"TEXT CALL KEY COUNT:  {len(text_payload)}")
            print(f"IMAGE CALL KEY COUNT: {len(image_payload)}")
            print(f"MODALITIES IN TEXT:   {'modalities' in text_payload}")
            print(f"MODALITIES IN IMAGE:  {'modalities' in image_payload}")
            print("--------------------------\n")

if __name__ == "__main__":
    unittest.main()
