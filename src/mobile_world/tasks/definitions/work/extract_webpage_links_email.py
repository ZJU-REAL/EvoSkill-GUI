"""Extract webpage links and send email with the list."""

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class ExtractWebpageLinksEmailTask(BaseTask):
    """Extract all links from webpage and send email with comma-separated links."""

    goal = (
        "获取网页https://yenanliu.github.io/AVSS.github.io/的所有子链接，"
        "用英文逗号分隔返回，例如：url1,url2,url3，"
        "把得到的链接发送到chen@gmail.com，自拟邮件标题。"
    )
    task_tags = {"agent-mcp", "lang-cn"}

    WEBPAGE_URL = "https://yenanliu.github.io/AVSS.github.io/"
    EMAIL_ADDRESS = "chen@gmail.com"
    LINKS = [
        "https://scholar.google.com/citations?hl=zh-CN&user=HmvE2WsAAAAJ",
        "https://gogoduck912.github.io/",
        "https://scholar.google.com/citations?user=DkAZJX4AAAAJ&hl=zh-CN",
        "https://scholar.google.com/citations?user=NYLsVscAAAAJ&hl=zh-CN",
        "https://staff.itee.uq.edu.au/huang/",
        "https://people.csiro.au/w/d/dadong-wang.aspx",
        "https://sites.google.com/view/xinyus-homepage/Home",
        "https://yenanliu.github.io/AVSS.github.io/static/images/pipline.jpg",
        "https://drive.google.com/drive/folders/1fV-P63iAg9BlkUB2_eTDrQT8JPZAj_My?usp=sharing",
    ]

    app_names = {"MCP-jina", "Mail"}

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        email = get_sent_email_info()
        if email is None:
            return 0.0, "No email sent"

        if email.get("to", "").lower() != self.EMAIL_ADDRESS.lower():
            return (
                0.0,
                f"Email sent to wrong address: {email.get('to')} (expected: {self.EMAIL_ADDRESS})",
            )

        email_body = email.get("body", "").strip()

        for link in self.LINKS:
            if link.lower() not in email_body.lower():
                return 0.0, f"Link {link} not found in email body"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
