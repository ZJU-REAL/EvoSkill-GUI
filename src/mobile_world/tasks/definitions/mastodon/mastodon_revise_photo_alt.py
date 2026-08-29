"""Revise the photo alternation on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonRevisePhotoAltTask(BaseTask):
    goal = (
        "please check the ALT content of the picture in the toot i posted about 'Impression, Sunrise' in Mastodon, "
        "if the author Monet is not mentioned, please add 'Author is Monet' to the first line"
    )

    EXPECTED_TOOT_ID = 115378662120962265
    EXPECTED_AUTHOR = "Monet"

    task_tags = {"lang-en"}

    app_names = {
        "Mastodon",
    }

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False
        return True

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        Check:
        - The photo alt contains the author's name
        - The author's name is mentioned in the first line of the photo alt
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)  # wait for the photo alt to be revised

        images = mastodon.get_images_by_status_id(self.EXPECTED_TOOT_ID)
        if not images:
            return 0.0, f"No images found for toot: {self.EXPECTED_TOOT_ID}"

        image = images[0]
        image_alt = str(image.get("description"))
        image_alt_first_line = image_alt.split("\n")[0]

        # check the author
        if self.EXPECTED_AUTHOR.lower() not in image_alt_first_line.lower():
            return (
                0.0,
                f"Author {self.EXPECTED_AUTHOR} not found in the image ALT(first line): {image_alt_first_line}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
        return True
