"""Tests for the /api/SKILL.md endpoint."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.public import router as public_router


app = FastAPI()
app.include_router(public_router)


class TestSkillEndpoint(unittest.TestCase):
    """Test suite for the SKILL.md API endpoint."""

    def test_skill_md_endpoint_returns_200(self) -> None:
        """Test that the SKILL.md endpoint returns 200 status code."""
        mock_content = "# Flowdeck\n\nTest content"
        
        with patch("builtins.open", mock_open(read_data=mock_content)):
            client = TestClient(app)
            response = client.get("/api/SKILL.md")
        
        self.assertEqual(response.status_code, 200)

    def test_skill_md_endpoint_returns_correct_content_type(self) -> None:
        """Test that the endpoint returns markdown content type."""
        mock_content = "# Flowdeck\n\nTest content"
        
        with patch("builtins.open", mock_open(read_data=mock_content)):
            client = TestClient(app)
            response = client.get("/api/SKILL.md")
        
        self.assertEqual(response.headers["content-type"], "text/markdown; charset=utf-8")

    def test_skill_md_endpoint_returns_file_content(self) -> None:
        """Test that the endpoint returns the actual file content."""
        mock_content = "# Flowdeck\n\nAI-powered ticker analysis platform"
        
        with patch("builtins.open", mock_open(read_data=mock_content)):
            client = TestClient(app)
            response = client.get("/api/SKILL.md")
        
        self.assertEqual(response.text, mock_content)

    def test_skill_md_endpoint_sets_cache_control_headers(self) -> None:
        """Test that the endpoint sets appropriate cache control headers."""
        mock_content = "# Flowdeck\n\nTest content"
        
        with patch("builtins.open", mock_open(read_data=mock_content)):
            client = TestClient(app)
            response = client.get("/api/SKILL.md")
        
        self.assertIn("cache-control", response.headers)
        self.assertEqual(response.headers["cache-control"], "public, max-age=3600")

    def test_skill_md_endpoint_sets_content_disposition(self) -> None:
        """Test that the endpoint sets content disposition header."""
        mock_content = "# Flowdeck\n\nTest content"
        
        with patch("builtins.open", mock_open(read_data=mock_content)):
            client = TestClient(app)
            response = client.get("/api/SKILL.md")
        
        self.assertIn("content-disposition", response.headers)
        self.assertEqual(response.headers["content-disposition"], 'inline; filename="SKILL.md"')

    def test_skill_md_endpoint_returns_404_when_file_not_found(self) -> None:
        """Test that the endpoint returns 404 when SKILL.md file is missing."""
        with patch("builtins.open", side_effect=FileNotFoundError("File not found")):
            client = TestClient(app)
            response = client.get("/api/SKILL.md")
        
        self.assertEqual(response.status_code, 404)
        self.assertIn("SKILL.md not found", response.json()["detail"])

    def test_skill_md_endpoint_handles_large_file(self) -> None:
        """Test that the endpoint can handle large SKILL.md files."""
        # Create a large mock content (simulate a comprehensive API doc)
        mock_content = "# Flowdeck\n\n" + ("API documentation line\n" * 1000)
        
        with patch("builtins.open", mock_open(read_data=mock_content)):
            client = TestClient(app)
            response = client.get("/api/SKILL.md")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.text), len(mock_content))

    def test_skill_md_endpoint_handles_unicode_content(self) -> None:
        """Test that the endpoint properly handles unicode characters."""
        mock_content = "# Flowdeck 📊\n\nAI-powered analysis with émojis and spëcial çharacters"
        
        with patch("builtins.open", mock_open(read_data=mock_content)):
            client = TestClient(app)
            response = client.get("/api/SKILL.md")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, mock_content)

    def test_skill_md_file_path_resolution(self) -> None:
        """Test that the file path is correctly resolved relative to the router file."""
        mock_content = "# Flowdeck\n\nTest content"
        
        with patch("builtins.open", mock_open(read_data=mock_content)) as mock_file:
            client = TestClient(app)
            response = client.get("/api/SKILL.md")
            
            # Verify the file was opened
            mock_file.assert_called_once()
            # Get the path that was used to open the file
            call_args = mock_file.call_args[0][0]
            
            # Verify it's a Path object or string ending with SKILL.md
            if isinstance(call_args, Path):
                self.assertTrue(str(call_args).endswith("SKILL.md"))
            else:
                self.assertTrue(call_args.endswith("SKILL.md"))


if __name__ == "__main__":
    unittest.main()

# Made with Bob
