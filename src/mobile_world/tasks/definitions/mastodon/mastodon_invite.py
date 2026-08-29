"""Report a toxic post on Mastodon."""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonInviteTask(BaseTask):
    goal = (
        "Generate a one-person invite link that expires in one day, "
        "auto-follows me, and send it to my friend Leonard by SMS."
    )

    EXPECTED_RECIPIENT_NUMBER = "+16265551427"
    EXPECTED_INVITE_VALIDITY_DAYS = 1
    EXPECTED_INVITE_MAX_USES = 1
    EXPECTED_AUTO_FOLLOW = True
    EXPECTED_AUTO_FOLLOW_USERNAME = "test"

    task_tags = {"lang-en"}

    app_names = {"Mastodon", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            mastodon.start_mastodon_backend()
            return True
        except Exception as e:
            logger.error(f"Failed to start Mastodon backend: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        """
        check:
        - invite validity days
        - invite max uses
        - invite auto-follow
        - SMS content recipient number
        - SMS content includes the invite link

        note:
        - if the expiration time is infinite, the database fields are null
        - only check the days level of the expiration time
        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        invites = mastodon.get_invite_info(self.EXPECTED_AUTO_FOLLOW_USERNAME)
        if not invites:
            return 0.0, "No invites returned."
        invite = invites[0]

        # check expiration, granularity: days
        expires_at = mastodon.parse_dt(invite.get("expires_at"))
        created_at = mastodon.parse_dt(invite.get("created_at"))
        if (
            not expires_at or not created_at
        ):  # ATTENTION: if set to infinite, the database fields are null
            return 0.0, "Invalid  expires_at or created_at in invite."
        delta_days = (expires_at.date() - created_at.date()).days
        if delta_days != self.EXPECTED_INVITE_VALIDITY_DAYS:
            return (
                0.0,
                f"Expiry days mismatch. expected={self.EXPECTED_INVITE_VALIDITY_DAYS}, got={delta_days}",
            )

        # check max uses
        max_uses = invite.get("max_uses")
        if not max_uses or max_uses != self.EXPECTED_INVITE_MAX_USES:
            return (
                0.0,
                f"Max uses mismatch. expected={self.EXPECTED_INVITE_MAX_USES}, got={max_uses}",
            )

        # check auto-follow
        autofollow = invite.get("autofollow")
        if autofollow != self.EXPECTED_AUTO_FOLLOW:
            return (
                0.0,
                f"Auto-follow mismatch. expected={self.EXPECTED_AUTO_FOLLOW}, got={autofollow}",
            )

        # check SMS content
        link = invite.get("invite_url")
        if not link:
            return 0.0, "Invite link not found."
        consistency = check_sms_via_adb(controller, self.EXPECTED_RECIPIENT_NUMBER, link)
        if not consistency:
            return 0.0, "SMS content mismatch."

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
