import os
import json
import urllib.request
import ssl
import re
import shutil
import zipfile
from typing import Tuple
from src.logger import create_logger

logger = create_logger()

DOWNLOADS_FOLDER = os.path.join(os.getcwd(), "Downloads")

UPDATE_LATEST_URL = (
    "https://api.github.com/repos/unrealities/MTGA_Draft_17Lands/releases/latest"
)
UPDATE_FILENAME = "MTGA_Draft_Tool_Setup.exe"

if not os.path.exists(DOWNLOADS_FOLDER):
    os.makedirs(DOWNLOADS_FOLDER)


class AppUpdate:
    def __init__(self):
        self.version: str = ""
        self.file_location: str = ""
        self.context: ssl.SSLContext = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
        self.context.load_default_certs()

    def retrieve_file_version(
        self, search_location: str = UPDATE_LATEST_URL
    ) -> Tuple[str, str]:
        """Retrieve the file version with strict timeout to prevent hangs."""
        self.version = ""
        self.file_location = ""
        try:
            # Added 2-second timeout. Startup should never hang on non-critical updates.
            with urllib.request.urlopen(
                search_location, context=self.context, timeout=2
            ) as response:
                url_data = response.read()
                url_json = json.loads(url_data)
                self.__process_file_version(url_json)
        except Exception as error:
            logger.error(f"AppUpdate network error: {error}")
        return self.version, self.file_location

    def download_file(
        self, input_url: str, output_filename: str = UPDATE_FILENAME
    ) -> str:
        """Download a file from Github"""
        output_location: str = ""
        try:
            input_filename = os.path.basename(input_url)
            temp_input_location = os.path.join(DOWNLOADS_FOLDER, input_filename)
            temp_output_location = os.path.join(DOWNLOADS_FOLDER, output_filename)

            with urllib.request.urlopen(input_url, context=self.context) as response:
                with open(temp_input_location, "wb") as file:
                    shutil.copyfileobj(response, file)

            if zipfile.is_zipfile(temp_input_location):
                with zipfile.ZipFile(temp_input_location, "r") as zip_ref:
                    file = zip_ref.infolist()[0]
                    file.filename = output_filename
                    zip_ref.extract(file, DOWNLOADS_FOLDER)
            else:
                os.replace(temp_input_location, temp_output_location)

            if os.path.exists(temp_output_location):
                output_location = temp_output_location
        except Exception as error:
            logger.error(error)

        return output_location

    def __process_file_version(self, release: dict) -> None:
        try:
            # 1. Grab the download URL immediately so it's never skipped
            self.file_location = release["assets"][0]["browser_download_url"]

            # 2. Try the modern Semantic Tag approach first (v4.05, v3.2, etc.)
            tag_name = release.get("tag_name", "")
            match = re.search(r"(\d+\.\d+)", tag_name)

            if match:
                self.version = match.group(1)
            else:
                # 3. Fallback to legacy filename parsing (MTGA_Draft_Tool_V0320.zip -> 0320)
                filename = release["assets"][0]["name"]
                nums = re.findall(r"\d+", filename)
                if nums:
                    version_code = nums[0]
                    if len(version_code) >= 3:
                        self.version = str(float(version_code) / 100.0)
                    else:
                        self.version = version_code

        except Exception as error:
            logger.error(f"Version parsing error: {error}")
