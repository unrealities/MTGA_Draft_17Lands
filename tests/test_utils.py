import unittest
from unittest.mock import patch, MagicMock
from PIL import Image
import base64
import os
import tempfile
from io import BytesIO
from src.utils import capture_screen_base64str
from src.constants import SCREENSHOT_FOLDER

class TestCaptureScreenBase64Str(unittest.TestCase):

    @patch('PIL.ImageGrab.grab')
    @patch('time.time', return_value=1625077765)
    @patch('os.path.join', return_value='screenshots/screenshot_1625077765.png')
    def test_capture_screen_base64str_no_persist(self, mock_grab):
        # Setup mock image
        mock_image = MagicMock(spec=Image.Image)
        mock_grab.return_value = mock_image

        # Create a mock buffer to simulate image save and base64 encoding
        mock_buffer = BytesIO()
        mock_image.save.side_effect = lambda buf, fmt: mock_buffer.write(b'test_image_data')

        result = capture_screen_base64str(persist=False)

        # Ensure the function returns the expected base64 string
        expected_base64 = base64.b64encode(b'test_image_data').decode("utf-8")
        self.assertEqual(result, expected_base64)

        # Ensure image save is called once
        mock_image.save.assert_called_once_with(mock_buffer, format="PNG")

    @patch('PIL.ImageGrab.grab')
    @patch('time.time', return_value=1625077765)
    @patch('os.path.join', return_value='screenshots/screenshot_1625077765.png')
    def test_capture_screen_base64str_with_persist(self, mock_grab):
        # Setup mock image
        mock_image = MagicMock(spec=Image.Image)
        mock_grab.return_value = mock_image

        # Create a mock buffer to simulate image save and base64 encoding
        mock_buffer = BytesIO()
        mock_image.save.side_effect = lambda buf, fmt: mock_buffer.write(b'test_image_data')

        # Create a temporary directory to save the screenshot
        with tempfile.TemporaryDirectory() as tempdir:
            global SCREENSHOT_FOLDER
            original_screenshot_folder = SCREENSHOT_FOLDER
            SCREENSHOT_FOLDER = tempdir

            # Ensure the temporary directory exists
            os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)

            result = capture_screen_base64str(persist=True)

            # Ensure the function returns the expected base64 string
            expected_base64 = base64.b64encode(b'test_image_data').decode("utf-8")
            self.assertEqual(result, expected_base64)

            # Ensure image save is called twice (once for the buffer and once for the file)
            self.assertEqual(mock_image.save.call_count, 2)

            # Check that the file was created
            expected_filename = os.path.join(tempdir, 'screenshot_1625077765.png')
            self.assertTrue(os.path.exists(expected_filename))

            # Clean up: restore the original SCREENSHOT_FOLDER
            SCREENSHOT_FOLDER = original_screenshot_folder
