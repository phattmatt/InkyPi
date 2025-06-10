import os
from utils.app_utils import resolve_path, get_font
from plugins.base_plugin.base_plugin import BasePlugin
from plugins.calendar.constants import LOCALE_MAP
from PIL import Image, ImageColor, ImageDraw, ImageFont
import icalendar
import recurring_ical_events
from io import BytesIO
import logging
import requests
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

class Calendar(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        template_params['locale_map'] = LOCALE_MAP
        return template_params

    def generate_image(self, settings, device_config):
        calendar_urls = settings.get('calendarURLs[]')
        calendar_colors = settings.get('calendarColors[]')
        view = settings.get("view")

        if not view:
            raise RuntimeError("View is required")
        elif view not in ["timeGridDay", "timeGridWeek", "dayGridMonth", "listMonth"]:
            raise RuntimeError("Invalid view")

        if not calendar_urls:
            raise RuntimeError("At least one calendar URL is required")
        for url in calendar_urls:
            if not url.strip():
                raise RuntimeError("Invalid calendar URL")

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]
        
        timezone = device_config.get_config("timezone", default="America/New_York")
        time_format = device_config.get_config("time_format", default="12h")
        tz = pytz.timezone(timezone)

        current_dt = datetime.now(tz)
        
        #current_time = 
        events = self.fetch_ics_events(calendar_urls, calendar_colors, tz)
        if not events:
            logger.warn("No events found for ics url")
        
        template_params = {}
        template_params["events"] = events
        template_params["view"] = view
        template_params["current_dt"] = current_dt.isoformat()
        template_params["timezone"] = timezone
        template_params["plugin_settings"] = settings

        image = self.render_image(dimensions, "calendar.html", "calendar.css", template_params)

        if not image:
            raise RuntimeError("Failed to take screenshot, please check logs.")
        return image
    
    def fetch_ics_events(self, calendar_urls, colors, tz):
        parsed_events = []

        now = datetime.utcnow()
        start_range = now - timedelta(days=7)
        end_range = now + timedelta(days=30)

        for calendar_url, color in zip(calendar_urls, colors):
            cal = self.fetch_calendar(calendar_url)
            events = recurring_ical_events.of(cal).between(start_range, end_range)

            for event in events:
                start, end, all_day = self.parse_data_points(event, tz)
                if(str(event.get("summary")) == 'Recurring Event'):
                    print(event.get('dtstart'), event.get('dtend'), event.get('duration'))
                parsed_event = {
                    "title": str(event.get("summary")),
                    "start": start,
                    "color": color,
                    "allDay": all_day
                }
                if end:
                    parsed_event['end'] = end

                parsed_events.append(parsed_event)

        return parsed_events
    
    #def determine_start_end(self, )
    
    def parse_data_points(self, event, tz):
        all_day = False
        dtstart = event.decoded("dtstart")
        if isinstance(dtstart, datetime):
            start = dtstart.astimezone(tz).isoformat()
        else:
            start = dtstart.isoformat()
            all_day = True

        end = None
        if "dtend" in event:
            dtend = event.decoded("dtend")
            if isinstance(dtend, datetime):
                end = dtend.astimezone(tz).isoformat()
            else:
                end = dtend.isoformat()
        elif "duration" in event:
            duration = event.decoded("duration")
            end = (dtstart + duration).isoformat()
        return start, end, all_day

    def fetch_calendar(self, calendar_url):
        try:
            response = requests.get(calendar_url)
            response.raise_for_status()
            return icalendar.Calendar.from_ical(response.text)
        except Exception as e:
            raise RuntimeError(f"Failed to fetch iCalendar url: {str(e)}")