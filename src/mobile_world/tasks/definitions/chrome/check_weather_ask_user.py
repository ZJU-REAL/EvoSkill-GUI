from datetime import datetime, timedelta, timezone

import requests
from loguru import logger

from mobile_world.runtime.app_helpers.system import (
    reset_chrome,
    time_sync_to_now,
)
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ChromeSearchBeijingWeatherAskUserTask(BaseTask):
    """Use Chrome to search for travel destination weather and ask user for the destination."""

    task_tags = {"agent-user-interaction", "lang-en"}
    goal = "What will be the maximum temperature at my hometown tomorrow? Answer with only an integer (the number of Celsius degree) and no other text."

    hometown = "Beijing"
    tolerance = 2.0

    app_names = {
        "Chrome",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            time_sync_to_now()

            reset_chrome(controller)

            self.relevant_information = f"My hometown is {self.hometown}. Today is {datetime.now().strftime('%Y-%m-%d')}."  # use the real date instead of hardcoded date
            return True
        except Exception as e:
            logger.error(f"Initialize Chrome task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        answer = controller.interaction_cache
        logger.info(f"Got answer from interaction_cache: '{answer}'")

        if not answer or answer.strip() == "":
            logger.error(
                "interaction_cache is empty! The agent should provide the temperature as an integer."
            )
            return (
                0.0,
                "interaction_cache is empty! The agent should provide the temperature as an integer.",
            )

        try:
            answer = int(answer)
            logger.info(f"Converted answer to int: {answer}")
        except Exception as e:
            logger.error(f"Failed to convert answer '{answer}' to int: {e}")
            logger.error(
                "The answer should be a valid integer representing the temperature in Celsius."
            )
            return 0.0, f"Failed to convert answer '{answer}' to int: {e}"

        if validate_answer_with_api_max(answer, self.tolerance):
            logger.info("Answer validation successful!")
            return 1.0, "Success"
        else:
            logger.error("Answer validation failed!")
            return 0.0, "Answer validation failed!"

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            reset_chrome(controller)
        except Exception as e:
            logger.error(f"Chrome tear_down failed: {e}")
            return False
        return True


def fetch_beijing_max_temp_tomorrow():
    """Fetch Beijing's maximum temperature for tomorrow."""
    logger.info("Fetching Beijing's max temperature for tomorrow from API...")
    lat, lon = 39.9042, 116.4074
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max",
        "timezone": "Asia/Shanghai",
    }

    try:
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()
        logger.info("API response received successfully")
    except Exception as e:
        logger.error(f"Failed to fetch data from API: {e}")
        raise

    daily = data.get("daily", {})
    temps = daily.get("temperature_2m_max", [])
    dates = daily.get("time", [])

    if not temps or not dates:
        logger.error("Open-Meteo daily data not available")
        raise RuntimeError("Open-Meteo daily data not available")

    logger.info(f"Got temperature data for dates: {dates}")

    # Get tomorrow's date
    tomorrow_str = (datetime.now(tz=timezone(timedelta(hours=8))) + timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )
    logger.info(f"Looking for tomorrow's date: {tomorrow_str}")

    for d, tmax in zip(dates, temps):
        if d == tomorrow_str:
            logger.info(f"Found tomorrow's highest temperature: {tmax}°C")
            return float(tmax)

    # If tomorrow's data not found, return the second day's data
    logger.warning("Tomorrow's date not found in API response, using fallback")
    if len(temps) > 1:
        logger.info(f"Using second day's temperature: {temps[1]}°C")
        return float(temps[1])
    logger.info(f"Using first day's temperature: {temps[0]}°C")
    return float(temps[0])


def validate_answer_with_api_max(answer: int, tolerance: float = 3.0) -> bool:
    """Validate the answer against API data for tomorrow's max temperature."""
    logger.info(f"Validating answer: {answer} (tolerance: ±{tolerance}°C)")

    try:
        api_max = fetch_beijing_max_temp_tomorrow()
        logger.info(f"Tomorrow's max temp from API: {api_max}°C")

        diff = abs(answer - api_max)
        is_valid = diff <= tolerance

        logger.info(f"Difference: {diff}°C, Valid: {is_valid}")
        return is_valid
    except Exception as e:
        logger.error(f"Error during validation: {e}")
        raise
