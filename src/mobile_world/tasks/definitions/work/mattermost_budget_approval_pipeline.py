"""Budget approval pipeline task - analyze budget requests and set up approval workflow."""

import re
import time

from mobile_world.runtime.app_helpers import mattermost
from mobile_world.runtime.app_helpers.mattermost import DEFAULT_PASSWORD, USERS
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


def compute_roi(npv: float, initial_investment: float) -> float:
    """Compute ROI: (NPV - I0) / I0 × 100."""
    return ((npv - initial_investment) / initial_investment) * 100


class MattermostBudgetApprovalPipelineTask(BaseTask):
    """Process budget approval requests with ROI calculations and configure approval workflow."""

    task_tags = {"lang-en"}
    goal = (
        "Review the 'budget-approvals-q4' channel for budget requests from different departments. "
        "Each request includes ROI calculations using mathematical formulas.\n\n"
        "Your tasks:\n"
        "1. Identify all budget requests that exceed $50,000 (these require executive approval).\n"
        "2. Calculate and identify which department has the HIGHEST projected ROI based on the "
        "NPV (Net Present Value) formula results posted in the channel.\n"
        "3. Post a consolidated budget summary in the channel with a markdown table showing:\n"
        "   - Department name\n"
        "   - Requested amount\n"
        "   - Projected ROI\n"
        "   - Approval status (Executive Required or Standard)"
    )
    # Ground-truth final table (ROI = (NPV - I0) / I0 * 100):
    # | Department  | Amount   | ROI | Approval Status    |
    # |-------------|----------|-----|--------------------|
    # | Engineering | $85,000  | 50% | Executive Required |
    # | Marketing   | $62,000  | 25% | Executive Required |
    # | HR          | $35,000  | 20% | Standard           |
    # | Operations  | $78,000  | 20% | Executive Required |
    # | Research    | $45,000  | 30% | Standard           |
    # Highest ROI: Engineering (50%)
    snapshot_tag = "init_state"

    CHANNEL_NAME = "budget-approvals-q4"
    EXECUTIVE_THRESHOLD = 50000

    # Budget requests - ROI computed dynamically from NPV and initial investment
    BUDGET_REQUESTS: dict[str, dict[str, float]] = {
        "Engineering": {
            "amount": 85000,
            "initial_investment": 85000,
            "npv": 127500,
        },
        "Marketing": {
            "amount": 62000,
            "initial_investment": 62000,
            "npv": 77500,
        },
        "HR": {
            "amount": 35000,
            "initial_investment": 35000,
            "npv": 42000,
        },
        "Operations": {
            "amount": 78000,
            "initial_investment": 78000,
            "npv": 93600,
        },
        "Research": {
            "amount": 45000,
            "initial_investment": 45000,
            "npv": 58500,
        },
    }

    def __init__(self):
        super().__init__()
        # Compute ROI dynamically for each department
        self._dept_roi: dict[str, float] = {}
        for dept, data in self.BUDGET_REQUESTS.items():
            self._dept_roi[dept] = compute_roi(data["npv"], data["initial_investment"])

        # Identify departments requiring executive approval (amount > threshold)
        self._executive_required = [
            dept
            for dept, data in self.BUDGET_REQUESTS.items()
            if data["amount"] > self.EXECUTIVE_THRESHOLD
        ]

        # Find highest ROI department
        self._highest_roi_dept = max(self._dept_roi.items(), key=lambda x: x[1])
        self._highest_roi_name = self._highest_roi_dept[0]
        self._highest_roi_value = self._highest_roi_dept[1]

        # Sort departments by ROI descending
        self._sorted_by_roi = sorted(self._dept_roi.items(), key=lambda x: x[1], reverse=True)

    app_names = {
        "Mattermost",
    }

    def _build_dept_message(self, dept: str) -> str:
        """Build a message for a department with computed ROI."""
        data = self.BUDGET_REQUESTS[dept]
        amount = int(data["amount"])
        npv = int(data["npv"])
        roi = self._dept_roi[dept]

        needs_exec = amount > self.EXECUTIVE_THRESHOLD
        approval_status = (
            "- *Requires Executive Approval*" if needs_exec else "- *Standard Approval*"
        )

        emoji_map = {
            "Engineering": "🔧",
            "Marketing": "📣",
            "HR": "👥",
            "Operations": "⚙️",
            "Research": "🔬",
        }
        emoji = emoji_map.get(dept, "📋")

        roi_emoji = "🚀" if roi >= 40 else "📈" if roi >= 25 else "📊"

        # Build item breakdown (simplified)
        items = self._get_dept_items(dept)
        item_rows = "\n".join(f"| {item} | ${val:,} |" for item, val in items)

        return (
            f"#### {emoji} {dept} Department Request\n\n"
            f"| Item | Amount |\n"
            f"|------|--------|\n"
            f"{item_rows}\n"
            f"| **Total** | **${amount:,}** |\n\n"
            f"**NPV Analysis** (r = 10%, n = 3 years):\n"
            f"NPV = {npv}"
            "\n\n"
            f"$ROI = \\frac{{{npv} - {amount}}}{{{amount}}} \\times 100 = {roi:.0f}\\%$"
            f"\n\n{roi_emoji} **Projected ROI: {roi:.0f}%**\n"
            f"{approval_status}"
        )

    def _get_dept_items(self, dept: str) -> list[tuple[str, int]]:
        """Get breakdown items for a department."""
        items_map = {
            "Engineering": [
                ("Cloud Infrastructure", 45000),
                ("Developer Tools", 25000),
                ("Training", 15000),
            ],
            "Marketing": [
                ("Ad Campaigns", 35000),
                ("Brand Refresh", 18000),
                ("Analytics Tools", 9000),
            ],
            "HR": [
                ("Recruitment Platform", 20000),
                ("Employee Wellness", 10000),
                ("Training Programs", 5000),
            ],
            "Operations": [
                ("Supply Chain Software", 40000),
                ("Warehouse Automation", 28000),
                ("Process Optimization", 10000),
            ],
            "Research": [
                ("Lab Equipment", 25000),
                ("Research Materials", 12000),
                ("Publications", 8000),
            ],
        }
        return items_map.get(dept, [])

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        mattermost.start_mattermost_backend()
        time.sleep(5)

        cli = mattermost.MattermostCLI()
        cli.login(USERS["alex"], DEFAULT_PASSWORD)

        cli.create_channel(
            team=mattermost.TEAM_NAME,
            channel_name=self.CHANNEL_NAME,
            display_name="Budget Approvals Q4",
            private=False,
            purpose="Q4 Budget requests and approvals",
        )
        cli.add_users_to_channel(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            users=["harry.kong@neuralforge.ai", USERS["sofia"], USERS["mike"], USERS["sam"]],
        )

        # Introduction with NPV/ROI formulas
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=(
                "# 💰 Q4 Budget Approval Pipeline\n\n"
                "**Approval Thresholds:**\n"
                f"- Requests ≤ ${self.EXECUTIVE_THRESHOLD:,}: Standard manager approval\n"
                f"- Requests > ${self.EXECUTIVE_THRESHOLD:,}: Executive approval required\n\n"
                "**ROI Calculation Formula:**\n"
                "$NPV = \\sum_{t=1}^{n} \\frac{CF_t}{(1+r)^t} - I_0$"
                "\n\n"
                "$ROI = \\frac{NPV - I_0}{I_0} \\times 100\\%$"
                "\n\nWhere:\n"
                "- $CF_t$ = Cash flow at time t"
                "\n"
                "- $r$ = Discount rate (10%)"
                "\n"
                "- $I_0$ = Initial investment"
            ),
        )

        # Sofia posts Engineering request (highest ROI)
        cli.logout()
        cli.login(USERS["sofia"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=self._build_dept_message("Engineering"),
        )

        # Mike posts Marketing request
        cli.logout()
        cli.login(USERS["mike"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=self._build_dept_message("Marketing"),
        )

        # Discussion noise
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="@sofia The engineering ROI looks very promising! What's the payback period?",
        )

        # Sam posts HR request (under threshold)
        cli.logout()
        cli.login(USERS["sam"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=self._build_dept_message("HR"),
        )

        # Alex posts Operations request
        cli.logout()
        cli.login(USERS["alex"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=self._build_dept_message("Operations"),
        )
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message="@sofia Payback period is approximately 18 months for engineering.",
        )

        # Sofia posts Research request (under threshold)
        cli.logout()
        cli.login(USERS["sofia"], DEFAULT_PASSWORD)
        cli.send_message(
            team=mattermost.TEAM_NAME,
            channel=self.CHANNEL_NAME,
            message=self._build_dept_message("Research"),
        )

        return True

    def _extract_table_data(self, msg_content: str) -> list[dict[str, str | float | None]]:
        """
        Extract department data from a markdown table.
        Returns list of dicts with department, amount, roi, approval_status.
        """
        results: list[dict[str, str | float | None]] = []
        lines = msg_content.split("\n")

        for line in lines:
            if "|" not in line or "---" in line:
                continue

            line_lower = line.lower()

            # Find which department this row is about
            dept_found = None
            for dept in self.BUDGET_REQUESTS:
                if dept.lower() in line_lower:
                    dept_found = dept
                    break

            if not dept_found:
                continue

            # Try to extract amount (look for $ or large numbers)
            amount_match = re.search(r"\$?([\d,]+)", line)
            amount = None
            if amount_match:
                try:
                    amount = float(amount_match.group(1).replace(",", ""))
                except ValueError:
                    pass

            # Try to extract ROI (look for % or numbers near "roi")
            roi_match = re.search(r"(\d+\.?\d*)\s*%", line)
            roi = None
            if roi_match:
                try:
                    roi = float(roi_match.group(1))
                except ValueError:
                    pass

            # Check approval status
            is_executive = (
                "executive" in line_lower
                or "exec" in line_lower
                or "> 50" in line_lower
                or ">50" in line_lower
            )
            is_standard = "standard" in line_lower

            results.append(
                {
                    "department": dept_found,
                    "amount": amount,
                    "roi": roi,
                    "is_executive": is_executive,
                    "is_standard": is_standard,
                }
            )

        return results

    def _verify_summary_content(self, msg_content: str) -> tuple[bool, str]:
        """
        Verify that the summary table contains correct information.
        Returns (is_valid, error_message).
        """
        table_data = self._extract_table_data(msg_content)

        if len(table_data) < 3:  # At least need the 3 executive departments
            return False, f"Table has insufficient rows ({len(table_data)})"

        # Check that all executive-required departments are present
        found_depts = {d["department"] for d in table_data}
        for exec_dept in self._executive_required:
            if exec_dept not in found_depts:
                return False, f"Missing executive department: {exec_dept}"

        # Verify ROI values are approximately correct (within 5% tolerance)
        for row in table_data:
            dept = row["department"]
            if dept and row["roi"] is not None:
                expected_roi = self._dept_roi.get(dept)
                if expected_roi is not None:
                    diff = abs(row["roi"] - expected_roi)
                    if diff > 5:  # Allow 5% tolerance
                        return (
                            False,
                            f"{dept} ROI mismatch: got {row['roi']}, expected {expected_roi:.0f}",
                        )

        return True, ""

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()
        assert mattermost.is_mattermost_healthy()

        # Check: Budget summary posted in channel with proper table
        channel_info = mattermost.get_channel_info(channel_name=self.CHANNEL_NAME)
        if not channel_info:
            return 0.0, f"Channel '{self.CHANNEL_NAME}' not found"

        messages = mattermost.get_latest_messages()[:15]
        channel_messages = [m for m in messages if m[5] == channel_info[0]]

        summary_found = False
        validation_error = ""

        for msg in channel_messages:
            msg_content = msg[8]
            msg_content_lower = msg_content.lower()

            # Must be a table and posted by Harry (the agent user)
            if "|" not in msg_content:
                continue
            if msg[4] != mattermost.HARRY_ID:
                continue

            # Check all executive departments are mentioned
            all_exec_present = all(
                dept.lower() in msg_content_lower for dept in self._executive_required
            )
            if not all_exec_present:
                continue

            # Must have ROI info (% sign or "roi" keyword)
            has_roi_info = "%" in msg_content or "roi" in msg_content_lower

            if not has_roi_info:
                continue

            summary_found = True

            # Validate content accuracy
            is_valid, error = self._verify_summary_content(msg_content)
            if is_valid:
                return 1.0
            else:
                validation_error = error

        if not summary_found:
            return (
                0.0,
                "Budget summary table not posted in channel (missing departments, ROI info, or table format)",
            )

        if validation_error:
            return 0.0, f"Summary table content validation failed: {validation_error}"

        return 1.0

    def tear_down(self, controller: AndroidController) -> bool:
        super().tear_down(controller)
        mattermost.stop_mattermost_backend()
        return True
