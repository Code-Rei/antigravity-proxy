import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.services.image_service import resolve_aspect_ratio
from app.services.transform import transform_to_google_body, resolve_target_model
from config import IMAGE_MODELS, SUPPORTED_MODELS

class TestAntigravityProxy(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_aspect_ratio_resolution(self):
        self.assertEqual(resolve_aspect_ratio("1024x1024"), "1:1")
        self.assertEqual(resolve_aspect_ratio("1792x1024"), "16:9")
        self.assertEqual(resolve_aspect_ratio("1024x1792"), "9:16")
        self.assertEqual(resolve_aspect_ratio("4:3"), "4:3")
        self.assertEqual(resolve_aspect_ratio("unknown"), "1:1")
        self.assertEqual(resolve_aspect_ratio(None), "1:1")

    def test_model_resolution(self):
        self.assertEqual(resolve_target_model("nano-banana-2"), "gemini-3-pro-image")
        self.assertEqual(resolve_target_model("gemini-3-pro-image"), "gemini-3-pro-image")
        self.assertEqual(resolve_target_model("claude-sonnet-4-6"), "claude-sonnet-4-6-thinking")
        self.assertEqual(resolve_target_model("gemini-3-flash"), "gemini-3-flash")
        self.assertEqual(resolve_target_model("gemini-3-pro-low"), "gemini-3-pro-low")

    def test_models_endpoint(self):
        response = self.client.get("/v1/models")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("object"), "list")
        model_ids = [m["id"] for m in data.get("data", [])]
        self.assertIn("nano-banana-2", model_ids)
        self.assertIn("gemini-3-pro-image", model_ids)
        self.assertIn("gemini-3-pro-high", model_ids)

    def test_api_status_endpoint(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertIn("nano-banana-2", data.get("image_models", []))

    def test_transform_to_google_body(self):
        openai_req = {
            "model": "gemini-3-pro-high",
            "messages": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Hello!"}
            ],
            "temperature": 0.5
        }
        google_body = transform_to_google_body(openai_req, project_id="test-proj")
        self.assertEqual(google_body["project"], "test-proj")
        self.assertEqual(google_body["model"], "gemini-3-pro-high")
        self.assertIn("generationConfig", google_body)
        self.assertEqual(google_body["generationConfig"]["thinkingConfig"]["thinkingLevel"], "high")
        self.assertEqual(len(google_body["contents"]), 1)
        self.assertEqual(google_body["contents"][0]["role"], "user")

if __name__ == "__main__":
    unittest.main()
