"""Compare apartment distances and send SMS with result."""

import time

from mobile_world.runtime.app_helpers import mcp as mcp_helper
from mobile_world.runtime.app_helpers.system import check_sms_via_adb
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CompareApartmentsDistanceSmsTask(BaseTask):
    """Compare two apartments' distance to company and send SMS with result."""

    goal = (
        "中介给我发了两套房子的信息，我想比较一下哪一套离阿里西溪c园区开车更近，好决定租哪一间。"
        "把最近那套房子的地址发给我朋友 Mia"
    )
    task_tags = {"agent-mcp", "lang-cn"}

    RECIPIENT_PHONE = "14058298746"
    COMPANY_LOCATION = "120.140446,30.280180"
    APARTMENT1_LOCATION = "120.097675,30.287514"
    APARTMENT2_LOCATION = "120.106899,30.286377"

    SMS_2 = "第二套公寓：杭州市西湖区雅仕苑 - 环境优美，配套齐全，月租5200元，高品质生活从这里开始！"
    SMS_1 = "第一套公寓：杭州市西湖区华苑公寓 - 精装修两居室，临近地铁2号线古墩路站，周边商超齐全，交通便利，月租4800元，拎包入住！是您理想的居住选择！"

    app_names = {"MCP-Amap", "Messages"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        controller.simulate_sms(
            sender="15858101234",
            message=self.SMS_1,
        )
        controller.simulate_sms(
            sender="15858101234",
            message=self.SMS_2,
        )
        time.sleep(2)
        return True

    async def is_successful_async(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        company_location = self.COMPANY_LOCATION
        apt1_location = self.APARTMENT1_LOCATION
        apt2_location = self.APARTMENT2_LOCATION

        distance_data = await mcp_helper.calculate_distance(
            origins=f"{apt1_location}|{apt2_location}", destination=company_location
        )

        dist1 = int(distance_data["results"][0].get("distance", 0))
        dist2 = int(distance_data["results"][1].get("distance", 0))

        expected_content = "雅仕苑" if dist1 < dist2 else "华苑公寓"

        if not check_sms_via_adb(
            controller, phone_number=self.RECIPIENT_PHONE, content=expected_content
        ):
            return (
                0.0,
                f"SMS not found sent to {self.RECIPIENT_PHONE} with expected content: {expected_content}",
            )

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        return True
