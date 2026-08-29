import re

import requests
from loguru import logger

from mobile_world.runtime.app_helpers.mail import get_sent_email_info
from mobile_world.runtime.app_helpers.system import reset_chrome
from mobile_world.runtime.controller import AndroidController
from mobile_world.tasks.base import BaseTask


class CheckGithubInfoTask(BaseTask):
    """Check AndroidWorld GitHub repository stats and send email with the information."""

    goal = (
        "Please check the number of stars and contributors on the AndroidWorld GitHub repository, then send an email to kevin_zhang@example.com "
        'with the subject line "AndroidWorld Repository Stats" and the following message body:\n'
        "There are XXX stars and XXX contributors in the AndroidWorld repository.\n\n"
        'Replace "XXX" with the actual numbers you find.'
    )

    # Expected email details
    correct_recipient = "kevin_zhang@example.com"
    expected_subject = "AndroidWorld Repository Stats"

    # GitHub repository information
    github_owner = "google-research"
    github_repo = "android_world"

    task_tags = {"lang-en"}

    app_names = {"Chrome", "Mail"}

    def initialize_task_hook(self, controller: AndroidController) -> bool:
        try:
            reset_chrome(controller)

            return True
        except Exception as e:
            logger.error(f"Initialize Chrome task failed: {e}")
            return False

    def is_successful(self, controller: AndroidController) -> float | tuple[float, str]:
        self._check_is_initialized()

        logger.info("Checking for sent email...")
        email = get_sent_email_info()

        if email is None:
            logger.info("No email found")
            return 0.0, "No email found"

        logger.info(f"Found email - To: {email.get('to')}, Subject: {email.get('subject')}")

        if email["to"].lower() != self.correct_recipient.lower():
            logger.info(f"Email sent to wrong recipient: {email['to']}")
            return 0.0, f"Email sent to wrong recipient: {email['to']}"

        email_subject = email.get("subject", "")
        if self.expected_subject.lower() not in email_subject.lower():
            logger.info(f"Email subject incorrect: {email_subject}")
            return 0.0, f"Email subject incorrect: {email_subject}"

        email_body = email.get("body", "")
        logger.info(f"Email body: {email_body}")

        logger.info("Fetching GitHub stats for validation...")
        stars, contributors = fetch_github_stats(self.github_owner, self.github_repo)
        if stars is None or contributors is None:
            logger.warning("Failed to fetch GitHub stats from API")
            return 0.0, "Failed to fetch GitHub stats from API"

        if validate_email_content(email_body, stars, contributors):
            return 1.0, "Success"
        else:
            return (
                0.0,
                f"Email body has incorrect stats. Expected: {stars} stars, {contributors} contributors",
            )


def fetch_github_stats(owner: str, repo: str) -> tuple[int | None, int | None]:
    """Fetch stars and contributors count from GitHub API."""
    try:
        logger.info(f"Starting GitHub API query for repository: {owner}/{repo}")

        repo_url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "MobileWorld-Task"}

        logger.info(f"Fetching repository info from: {repo_url}")
        repo_response = requests.get(repo_url, headers=headers, timeout=10)
        logger.info(f"Repository API response status: {repo_response.status_code}")
        repo_response.raise_for_status()

        repo_data = repo_response.json()
        stars_count = repo_data.get("stargazers_count", 0)
        logger.info(f"Successfully fetched stars count: {stars_count}")

        contributors_url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
        logger.info(f"Fetching contributors info from: {contributors_url}")
        contributors_response = requests.get(
            contributors_url, headers=headers, params={"per_page": 1, "anon": "true"}, timeout=10
        )
        logger.info(f"Contributors API response status: {contributors_response.status_code}")
        contributors_response.raise_for_status()

        link_header = contributors_response.headers.get("Link", "")
        contributors_count = 0

        if "last" in link_header:
            logger.info(f"Found pagination Link header: {link_header}")
            match = re.search(r'page=(\d+)>; rel="last"', link_header)
            if match:
                contributors_count = int(match.group(1))
                logger.info(f"Parsed contributors count from pagination: {contributors_count}")
        else:
            contributors_data = contributors_response.json()
            contributors_count = len(contributors_data)
            logger.info(f"No pagination found, counted {contributors_count} contributors directly")

        logger.info(
            f"GitHub API query completed successfully - Stars: {stars_count}, Contributors: {contributors_count}"
        )
        return stars_count, contributors_count

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP error fetching GitHub stats: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Unexpected error fetching GitHub stats: {e}")
        return None, None


def validate_email_content(
    email_body: str, expected_stars: int, expected_contributors: int, tolerance_pct: float = 0.05
) -> bool:
    """Validate that email body contains correct stars and contributors count."""
    k_pattern = r"(\d+(?:\.\d+)?)\s*[kK]"
    k_matches = re.findall(k_pattern, email_body)

    num_pattern = r"\b(\d+(?:,\d+)*)\b"
    num_matches = re.findall(num_pattern, email_body)

    parsed_numbers = []

    for k_num in k_matches:
        parsed_numbers.append(int(float(k_num) * 1000))

    for num in num_matches:
        clean_num = num.replace(",", "")
        if clean_num and clean_num not in [str(int(float(k) * 1000)) for k in k_matches]:
            parsed_numbers.append(int(clean_num))

    if len(parsed_numbers) < 2:
        logger.info(f"Email body doesn't contain enough numbers: {email_body}")
        logger.info(f"Found numbers: {parsed_numbers}")
        return False

    logger.info(f"Parsed numbers from email: {parsed_numbers}")

    stars_tolerance = max(int(expected_stars * tolerance_pct), 500)
    contributors_tolerance = 10

    for i in range(len(parsed_numbers)):
        for j in range(len(parsed_numbers)):
            if i == j:
                continue

            stars_in_email = parsed_numbers[i]
            contributors_in_email = parsed_numbers[j]

            stars_match = abs(stars_in_email - expected_stars) <= stars_tolerance
            contributors_match = (
                abs(contributors_in_email - expected_contributors) <= contributors_tolerance
            )

            if stars_match and contributors_match:
                return True

    return False
