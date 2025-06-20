"""
Wpotd Plugin for InkyPi
This plugin fetches the Wikipedia Picture of the Day (Wpotd) from Wikipedia's API
and displays it on the InkyPi device. It supports optional manual date selection or random dates.
"""

from plugins.base_plugin.base_plugin import BasePlugin
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import requests
import logging
from random import randint
from datetime import datetime, timedelta, date
from functools import lru_cache
from typing import Dict, Any

logger = logging.getLogger(__name__)

class Wpotd(BasePlugin):
    SESSION = requests.Session()
    HEADERS = {'User-Agent': 'InkyPi/0.0 (https://github.com/fatihak/InkyPi/)'}
    API_URL = "https://en.wikipedia.org/w/api.php"

    def generate_settings_template(self) -> Dict[str, Any]:
        template_params = super().generate_settings_template()
        template_params['style_settings'] = False
        return template_params

    def generate_image(self, settings: Dict[str, Any], device_config: Dict[str, Any]) -> Image.Image:
        logger.info(f"WPOTD plugin settings: {settings}")
        datetofetch = self._determine_date(settings)
        logger.info(f"WPOTD plugin datetofetch: {datetofetch}")

        data = self.fetch_potd(datetofetch)
        picurl = data["image_src"]
        logger.info(f"WPOTD plugin Picture URL: {picurl}")

        return self._download_image(picurl)

    def _determine_date(self, settings: Dict[str, Any]) -> date:
        if settings.get("randomizeWpotd") == "true":
            start = datetime(2015, 1, 1)
            delta_days = (datetime.today() - start).days
            return (start + timedelta(days=randint(0, delta_days))).date()
        elif settings.get("customDate"):
            return datetime.strptime(settings["customDate"], "%Y-%m-%d").date()
        else:
            return datetime.today().date()

    def _download_image(self, url: str) -> Image.Image:
        try:
            if url.lower().endswith(".svg"):
                logger.warning("SVG format is not supported by Pillow. Skipping image download.")
                raise RuntimeError("Unsupported image format: SVG.")

            response = self.SESSION.get(url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))
        except UnidentifiedImageError as e:
            logger.error(f"Unsupported image format at {url}: {str(e)}")
            raise RuntimeError("Unsupported image format.")
        except Exception as e:
            logger.error(f"Failed to load WPOTD image from {url}: {str(e)}")
            raise RuntimeError("Failed to load WPOTD image.")

    @lru_cache(maxsize=32)
    def fetch_potd(self, cur_date: date) -> Dict[str, Any]:
        title = f"Template:POTD/{cur_date.isoformat()}"
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "images",
            "titles": title
        }

        data = self._make_request(params)
        try:
            filename = data["query"]["pages"][0]["images"][0]["title"]
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to retrieve POTD filename for {cur_date}: {e}")
            raise RuntimeError("Failed to retrieve POTD filename.")

        image_src = self.fetch_image_src(filename)

        return {
            "filename": filename,
            "image_src": image_src,
            "image_page_url": f"https://en.wikipedia.org/wiki/{title}",
            "date": cur_date
        }

    @lru_cache(maxsize=64)
    def fetch_image_src(self, filename: str) -> str:
        params = {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": "url",
            "titles": filename
        }
        data = self._make_request(params)
        try:
            page = next(iter(data["query"]["pages"].values()))
            return page["imageinfo"][0]["url"]
        except (KeyError, IndexError, StopIteration) as e:
            logger.error(f"Failed to retrieve image URL for {filename}: {e}")
            raise RuntimeError("Failed to retrieve image URL.")

    def _make_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            response = self.SESSION.get(self.API_URL, params=params, headers=self.HEADERS, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Wikipedia API request failed with params {params}: {str(e)}")
            raise RuntimeError("Wikipedia API request failed.")