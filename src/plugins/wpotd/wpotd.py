"""
Wpotd Plugin for InkyPi
This plugin fetches the Wikipedia Picture of the Day (Wpotd) from Wikipedia's API
and displays it on the InkyPi device. It supports optional manual date selection or random dates.
"""

from plugins.base_plugin.base_plugin import BasePlugin
from PIL import Image
from io import BytesIO
import requests
import logging
from random import randint
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Wpotd(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = False
        return template_params

    def generate_image(self, settings, device_config):
        logger.info(f"WPOTD plugin settings: {settings}")

        params = {}

        if settings.get("randomizeWpotd") == "true":
            start = datetime(2015, 1, 1)
            end = datetime.today()
            delta_days = (end - start).days
            random_date = start + timedelta(days=randint(0, delta_days))
            params["date"] = random_date.strftime("%Y-%m-%d")
        elif settings.get("customDate"):
            params["date"] = settings["customDate"]

        data = self.fetch_potd(params["date"])

        try:
            img_data = requests.get(data["image_src"])
            image = Image.open(BytesIO(img_data.content))
        except Exception as e:
            logger.error(f"Failed to load APOD image: {str(e)}")
            raise RuntimeError("Failed to load APOD image.")

        return image
    
    def fetch_potd(self, cur_date):
        """
        Returns image data related to the current POTD
        """

        date_iso = cur_date.isoformat()
        title = "Template:POTD protected/" + date_iso

        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "images",
            "titles": title
        }

        response = requests.get(url="https://en.wikipedia.org/w/api.php", params=params)
        data = response.json()

        filename = data["query"]["pages"][0]["images"][0]["title"]
        image_src = self.fetch_image_src(filename)
        image_page_url = "https://en.wikipedia.org/wiki/Template:POTD_protected/" + date_iso

        image_data = {
            "filename": filename,
            "image_src": image_src,
            "image_page_url": image_page_url,
            "date": cur_date
        }

        return image_data


    def fetch_image_src(self, filename):
        """
        Returns the POTD's image url
        """

        params = {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": "url",
           "titles": filename
        }

        response = requests.get(url="https://en.wikipedia.org/w/api.php", params=params)
        data = response.json()
        page = next(iter(data["query"]["pages"].values()))
        image_info = page["imageinfo"][0]
        image_url = image_info["url"]

        return image_url