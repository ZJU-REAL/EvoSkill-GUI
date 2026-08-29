"""
Generate multiple invite links with different conditions.
"""

import time

from loguru import logger

from mobile_world.runtime.app_helpers import mastodon
from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class MastodonMultiInviteTask(BaseTask):
    goal = (
        "Generate two invite links with different conditions. "
        "One with validity days of 1 day and max uses of 1, "
        "send it to my friend Leonard by SMS. "
        "Another with validity days of 7 days and auto-follow me, "
        "send it to my friend Ella by SMS."
    )

    task_tags = {"lang-en"}
    EXPECTED_RECIPIENT_NUMBER_LEONARD = "+16265551427"
    EXPECTED_RECIPIENT_NUMBER_ELLA = "+14676741503"
    EXPECTED_INVITE_VALIDITY_DAYS_LEONARD = 1
    EXPECTED_INVITE_VALIDITY_DAYS_ELLA = 7
    EXPECTED_INVITE_MAX_USES_LEONARD = 1
    EXPECTED_AUTO_FOLLOW_LEONARD = False
    EXPECTED_AUTO_FOLLOW_ELLA = True
    EXPECTED_AUTO_FOLLOW_USERNAME = "test"

    app_names = {"Mastodon", "Messages"}

    @property
    def snapshot_tag(self) -> str | None:
        return "init_state"

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
        - Two invites are generated
        - Each invite has correct validity days
        - Each invite has correct max uses
        - Each invite has correct auto-follow setting
        - SMS content recipient number for Leonard
        - SMS content includes the invite link for Leonard
        - SMS content recipient number for Alla
        - SMS content includes the invite link for Alla

        """
        self._check_is_initialized()

        assert mastodon.is_mastodon_healthy()
        time.sleep(1)

        # Get the latest 2 invites
        invites = mastodon.get_invite_info(self.EXPECTED_AUTO_FOLLOW_USERNAME, limit=2)
        if not invites or len(invites) < 2:
            return 0.0, f"Expected 2 invites, but got {len(invites) if invites else 0}."

        # Identify which invite is for Leonard and which is for Alla
        # Based on validity days and auto-follow settings
        leonard_invite = None

        for invite in invites:
            expires_at = mastodon.parse_dt(invite.get("expires_at"))
            created_at = mastodon.parse_dt(invite.get("created_at"))
            if not expires_at or not created_at:
                continue

            delta_days = (expires_at.date() - created_at.date()).days
            max_uses = invite.get("max_uses")
            autofollow = invite.get("autofollow", False)

            # Match Leonard's invite: 1 day, max_uses=1, autofollow=False
            if (
                delta_days == self.EXPECTED_INVITE_VALIDITY_DAYS_LEONARD
                and max_uses == self.EXPECTED_INVITE_MAX_USES_LEONARD
                and autofollow == self.EXPECTED_AUTO_FOLLOW_LEONARD
            ):
                leonard_invite = invite
            # Match Ella's invite: 7 days, autofollow=True
            elif (
                delta_days == self.EXPECTED_INVITE_VALIDITY_DAYS_ELLA
                and autofollow == self.EXPECTED_AUTO_FOLLOW_ELLA
            ):
                ella_invite = invite

        if not leonard_invite:
            return 0.0, "Leonard's invite not found or doesn't match expected parameters."
        if not ella_invite:
            return 0.0, "Ella's invite not found or doesn't match expected parameters."

        # Verify Leonard's invite details
        leonard_expires_at = mastodon.parse_dt(leonard_invite.get("expires_at"))
        leonard_created_at = mastodon.parse_dt(leonard_invite.get("created_at"))
        if not leonard_expires_at or not leonard_created_at:
            return 0.0, "Invalid expires_at or created_at in Leonard's invite."
        leonard_delta_days = (leonard_expires_at.date() - leonard_created_at.date()).days
        if leonard_delta_days != self.EXPECTED_INVITE_VALIDITY_DAYS_LEONARD:
            return (
                0.0,
                f"Leonard's invite expiry days mismatch. expected={self.EXPECTED_INVITE_VALIDITY_DAYS_LEONARD}, got={leonard_delta_days}",
            )

        leonard_max_uses = leonard_invite.get("max_uses")
        if not leonard_max_uses or leonard_max_uses != self.EXPECTED_INVITE_MAX_USES_LEONARD:
            return (
                0.0,
                f"Leonard's invite max uses mismatch. expected={self.EXPECTED_INVITE_MAX_USES_LEONARD}, got={leonard_max_uses}",
            )

        leonard_autofollow = leonard_invite.get("autofollow")
        if leonard_autofollow != self.EXPECTED_AUTO_FOLLOW_LEONARD:
            return (
                0.0,
                f"Leonard's invite auto-follow mismatch. expected={self.EXPECTED_AUTO_FOLLOW_LEONARD}, got={leonard_autofollow}",
            )

        # Verify Alla's invite details
        ella_expires_at = mastodon.parse_dt(ella_invite.get("expires_at"))
        ella_created_at = mastodon.parse_dt(ella_invite.get("created_at"))
        if not ella_expires_at or not ella_created_at:
            return 0.0, "Invalid expires_at or created_at in Ella's invite."
        ella_delta_days = (ella_expires_at.date() - ella_created_at.date()).days
        if ella_delta_days != self.EXPECTED_INVITE_VALIDITY_DAYS_ELLA:
            return (
                0.0,
                f"Ella's invite expiry days mismatch. expected={self.EXPECTED_INVITE_VALIDITY_DAYS_ELLA}, got={ella_delta_days}",
            )

        ella_autofollow = ella_invite.get("autofollow")
        if ella_autofollow != self.EXPECTED_AUTO_FOLLOW_ELLA:
            return (
                0.0,
                f"Ella's invite auto-follow mismatch. expected={self.EXPECTED_AUTO_FOLLOW_ELLA}, got={ella_autofollow}",
            )

        # Check SMS content for Leonard
        leonard_link = leonard_invite.get("invite_url")
        if not leonard_link:
            return 0.0, "Leonard's invite link not found."
        leonard_sms_consistency = check_sms_via_adb(
            controller, self.EXPECTED_RECIPIENT_NUMBER_LEONARD, leonard_link
        )
        if not leonard_sms_consistency:
            return 0.0, "SMS content mismatch for Leonard."

        # Check SMS content for Sheldon
        ella_link = ella_invite.get("invite_url")
        if not ella_link:
            return 0.0, "Ella's invite link not found."
        ella_sms_consistency = check_sms_via_adb(
            controller, self.EXPECTED_RECIPIENT_NUMBER_ELLA, ella_link
        )
        if not ella_sms_consistency:
            return 0.0, "SMS content mismatch for Ella."

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        try:
            mastodon.stop_mastodon_backend()
        except Exception as e:
            logger.error(f"Failed to stop Mastodon backend: {e}")
            return False
        return True
