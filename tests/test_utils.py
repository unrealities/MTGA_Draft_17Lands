import unittest
from unittest.mock import patch, MagicMock
import os
import time
import base64
from io import BytesIO
from PIL import ImageGrab
from src.utils import capture_screen_base64str

SCREENSHOT_PREFIX = "test_"
SCREENSHOT_FOLDER = "/tests"

class TestCaptureScreenBase64str(unittest.TestCase):

    @patch('PIL.ImageGrab.grab')
    @patch('time.time')
    @patch('os.path.join')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_screenshot_persist(self, mock_open, mock_path_join, mock_time, mock_grab):
        # Arrange
        mock_image = MagicMock()
        mock_grab.return_value = mock_image
        mock_time.return_value = 1234567890
        mock_path_join.return_value = "/path/to/screenshot/folder/screenshot_1234567890"
        
        expected_filename = "/path/to/screenshot/folder/screenshot_1234567890"
        
        # Act
        base64str = capture_screen_base64str(True)
        
        # Assert
        mock_grab.assert_called_once()
        mock_time.assert_called_once()
        mock_path_join.assert_called_once_with(SCREENSHOT_FOLDER, SCREENSHOT_PREFIX + "1234567890")
        mock_image.save.assert_any_call(expected_filename, format="PNG")
        self.assertIsInstance(base64str, str)
        self.assertTrue(base64str.startswith("iVBORw0KGgo"))

    @patch('PIL.ImageGrab.grab')
    @patch('time.time')
    @patch('os.path.join')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    def test_screenshot_not_persist(self, mock_open, mock_path_join, mock_time, mock_grab):
        # Arrange
        mock_image = MagicMock()
        mock_grab.return_value = mock_image
        
        # Act
        base64str = capture_screen_base64str(False)
        
        # Assert
        mock_grab.assert_called_once()
        mock_time.assert_not_called()
        mock_path_join.assert_not_called()
        mock_image.save.assert_not_called()
        self.assertIsInstance(base64str, str)
        self.assertTrue(base64str.startswith("iVBORw0KGgo"))

if __name__ == '__main__':
    unittest.main()