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

    @patch("requests.post")
    def test_generate_image_with_reference_builds_multimodal_message(self, mock_post):
        # Mock successful base64 response
        fake_base64 = base64.b64encode(b"fake_png_bytes").decode()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"images": [{"image_url": {"url": f"data:image/png;base64,{fake_base64}"}}]}}]
        }
        
        reference = b"fake_reference_bytes"
        self.adapter.generate_image("A cat", reference_bytes=reference)
        
        # Verify payload messages structure
        payload = mock_post.call_args.kwargs["json"]
        messages = payload["messages"]
        self.assertEqual(len(messages), 1)
        content = messages[0]["content"]
        self.assertIsInstance(content, list)
        self.assertEqual(content[0]["type"], "image_url")
        self.assertEqual(content[1]["type"], "text")
        self.assertIn("visual style reference", content[1]["text"])

    @patch("requests.post")
    def test_generate_image_without_reference_builds_text_only_message(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"images": [{"image_url": {"url": "data:image/png;base64,AAA"}}]}}]
        }
        
        self.adapter.generate_image("A cat", reference_bytes=None)
        
        # Verify payload messages structure
        payload = mock_post.call_args.kwargs["json"]
        messages = payload["messages"]
        content = messages[0]["content"]
        self.assertIsInstance(content, str)
        self.assertEqual(content, "A cat")

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
