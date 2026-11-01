import json
import urllib.request
import ssl
import re
import certifi
from typing import Tuple
from src.logger import create_logger

logger = create_logger()

UPDATE_LATEST_URL = (
    "https://api.github.com/repos/unrealities/MTGA_Draft_17Lands/releases/latest"
)


class AppUpdate:
    def __init__(self):
        self.version: str = ""
        self.file_location: str = ""
        self.context: ssl.SSLContext = ssl.create_default_context(
            cafile=certifi.where()
        )

    def retrieve_file_version(
        self, search_location: str = UPDATE_LATEST_URL
    ) -> Tuple[str, str]:
        """Retrieve the file version with strict timeout to prevent hangs."""
        self.version = ""
        self.file_location = ""
        try:
            with urllib.request.urlopen(
                search_location, context=self.context, timeout=3
            ) as response:
                url_data = response.read()
                url_json = json.loads(url_data)
                self.__process_file_version(url_json)
        except Exception as error:
            logger.error(f"AppUpdate network error: {error}")
        return self.version, self.file_location

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
