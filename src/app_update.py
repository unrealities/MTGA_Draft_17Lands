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
        """Retrieve the file version"""
        self.version = ""
        self.file_location = ""
        try:
            url_data = urllib.request.urlopen(
                search_location, context=self.context
            ).read()
            url_json = json.loads(url_data)
            self.__process_file_version(url_json)
        except Exception as error:
            logger.error(error)
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
            filename = release["assets"][0]["name"]
            self.version = re.findall(r"\d+", filename, re.DOTALL)[0]
            self.file_location = release["assets"][0]["browser_download_url"]
        except Exception as error:
            logger.error(error)
        return
