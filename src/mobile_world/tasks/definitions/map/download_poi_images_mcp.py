"""Generate stock candidate list based on dividend rate and ESG rating."""

import re

import requests

import mobile_world.runtime.app_helpers.mattermost as mattermost
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class DownloadPoiImagesMcpTask(BaseTask):
    """Travel plan task."""

    goal = "帮我找到全国第一家Manner咖啡店，用高德mcp工具获取图片url和id，在mattermost上发给Sam并介绍一下这家店的历史（markdown格式）"
    task_tags = {"agent-mcp", "lang-cn"}
    POI_ID = "B0FFHIGY5F"
    MANNER_STARTUP_YEAR = "2015"

    app_names = {"MCP-Amap", "Chrome"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        mattermost.start_mattermost_backend()
        return True

    def _extract_image_urls_from_markdown(self, text: str) -> list[str]:
        """Extract image URLs from markdown format.

        Supports formats like:
        - ![alt text](url)
        - ![](url)
        - <img src="url">
        - Plain URLs ending with image extensions
        """
        urls = []

        # Match markdown image syntax: ![alt](url)
        markdown_pattern = r"!\[[^\]]*\]\(([^)]+)\)"
        urls.extend(re.findall(markdown_pattern, text))

        # Match HTML img tags: <img src="url"> or <img src='url'>
        html_pattern = r'<img[^>]+src=["\']([^"\']+)["\']'
        urls.extend(re.findall(html_pattern, text, re.IGNORECASE))

        # Match plain URLs that look like images
        url_pattern = r"https?://[^\s<>\[\]()]+\.(?:jpg|jpeg|png|gif|webp|bmp)(?:\?[^\s<>\[\]()]*)?"
        urls.extend(re.findall(url_pattern, text, re.IGNORECASE))

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def _validate_image_url(self, url: str, timeout: int = 10) -> bool:
        """Check if an image URL is valid and accessible.

        Args:
            url: The image URL to validate
            timeout: Request timeout in seconds

        Returns:
            True if the URL is accessible and returns a valid response
        """
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            if response.status_code == 200:
                return True
            # Some servers don't support HEAD, try GET
            response = requests.get(url, timeout=timeout, stream=True)
            return response.status_code == 200
        except requests.RequestException:
            return False

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        """Check if the task is successful."""
        self._check_is_initialized()
        assert mattermost.is_mattermost_healthy()

        latest_post = mattermost.get_latest_messages()[0]
        if (
            latest_post[4] != mattermost.HARRY_ID
            or latest_post[5] != mattermost.SAM_HARRY_CHANNEL_ID
        ):
            return 0.0, "Last message is not from harry to sam in the sam_harry channel"

        msg = latest_post[8]

        if self.POI_ID not in msg:
            return 0.0, "POI ID is not in the message"

        image_urls = self._extract_image_urls_from_markdown(msg)
        if not image_urls:
            return 0.0, "No image URLs found in the message"

        valid_url_found = False
        for url in image_urls:
            if self._validate_image_url(url):
                valid_url_found = True
                break

        if not valid_url_found:
            return 0.0, f"No valid/accessible image URLs found. URLs attempted: {image_urls}"

        if "manner" not in msg.lower() or self.MANNER_STARTUP_YEAR not in msg:
            return 0.0, "Manner is not in the message or startup year is not correct"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
        return True
