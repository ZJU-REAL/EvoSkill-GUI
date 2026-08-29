from datetime import datetime, timedelta, timezone

import requests
from loguru import logger

from mobile_world.runtime.app_helpers.system import reset_chrome
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ChromeSearchBeijingWeatherTask(BaseTask):
    """Use Chrome to search for 'Beijing weather today' and verify results appear."""

    goal = "Use Chrome to search for Beijing highest temperature today. ONLY give a integer number denoted Celsius degree."

    task_tags = {"lang-en"}

    app_names = {
        "Chrome",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            reset_chrome(controller)

            return True
        except Exception as e:
            logger.error(f"Initialize Chrome task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        answer = controller.interaction_cache

        try:
            answer = int(answer)
        except:
            return 0.0, f"Invalid answer: '{answer}'. Please answer with a integer number."

        if validate_answer_with_api_max(answer):
            return 1.0, "Success"
        else:
            return 0.0, "Answer validation failed!"


def fetch_beijing_max_temp():
    lat, lon = 39.9042, 116.4074
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max",
        "timezone": "Asia/Shanghai",
    }
    r = requests.get(url, params=params, timeout=8)
    r.raise_for_status()
    data = r.json()
    daily = data.get("daily", {})
    temps = daily.get("temperature_2m_max", [])
    dates = daily.get("time", [])
    if not temps or not dates:
        raise RuntimeError("Open-Meteo daily data not available")

    today_str = datetime.now(tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    for d, tmax in zip(dates, temps):
        if d == today_str:
            logger.info(f"Today's highest temperature: {tmax}")
            return float(tmax)

    return float(temps[0])


def validate_answer_with_api_max(answer: int, tolerance: float = 3.0) -> bool:
    api_max = fetch_beijing_max_temp()
    logger.info(f"max temp get from api: {api_max}")
    return abs(answer - api_max) <= tolerance
