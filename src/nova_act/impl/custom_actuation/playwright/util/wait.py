# Copyright 2025 Amazon Inc

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import time
from datetime import datetime, timezone

from playwright.sync_api import Page
from typing_extensions import Optional, TypedDict

from nova_act.impl.custom_actuation.playwright.util.image_helpers import (
    compare_images,
    take_screenshot_as_data_url,
)
from nova_act.impl.custom_actuation.playwright.util.take_observation import save_data_url_to_file
from nova_act.util.logging import setup_logging

_LOGGER = setup_logging(__name__)


def timed_wait(milliseconds: int, page: Page) -> None:
    page.wait_for_timeout(milliseconds)


class ConsecutiveChecksOptions(TypedDict):
    max_timeout_ms: Optional[int]  # in milliseconds
    number_of_checks: int
    percent_difference_threshold: float
    polling_interval_ms: int  # in milliseconds
    start_time: datetime


class PreviousAttempt(TypedDict):
    attempt_number: int
    screenshot: str


def delay(milliseconds: int) -> None:
    """Helper function to delay execution for a specified number of milliseconds."""
    time.sleep(milliseconds / 1000)


def consecutive_identical_checks(
    page: Page,
    options: ConsecutiveChecksOptions,
    previous_attempt: Optional[PreviousAttempt] = None,
    save_screenshot: Optional[bool] = False,
) -> None:
    """
    This function checks if the page has been unchanged for a certain number of checks.
    It will return when:
    1. The max timeout has been reached
    2. The page has been stable for the specified number of checks
    """

    # Check if max timeout has been reached
    if (
        options["max_timeout_ms"] is not None
        and options["max_timeout_ms"] > 0
        and (datetime.now().timestamp() - options["start_time"].timestamp()) * 1000 >= options["max_timeout_ms"]
    ):
        return

    # Take a screenshot of the current state
    screenshot = take_screenshot_as_data_url(page)
    if save_screenshot:
        if previous_attempt is not None:
            save_data_url_to_file(screenshot, f"screenshot_{previous_attempt['attempt_number']}.jpeg")
        else:
            save_data_url_to_file(screenshot, "screenshot_0.jpeg")

    if screenshot is None:
        raise Exception("Attempted to take a screenshot, but failed. Please try again.")

    # If this is the first attempt, wait and then try again
    if previous_attempt is None:
        delay(options["polling_interval_ms"])

        return consecutive_identical_checks(
            page,
            options,
            {"attempt_number": 1, "screenshot": screenshot},
            save_screenshot,
        )

    # Calculate the difference between the current and previous screenshots
    percent_difference = compare_images(previous_attempt["screenshot"], screenshot)

    # If the difference is below the threshold, return
    if percent_difference < options["percent_difference_threshold"]:
        return

    # If we've reached the required number of checks, we're done
    if previous_attempt["attempt_number"] >= options["number_of_checks"]:
        return

    # Otherwise, increment the counter and continue checking
    delay(options["polling_interval_ms"])

    return consecutive_identical_checks(
        page,
        options,
        {
            "attempt_number": previous_attempt["attempt_number"] + 1,
            "screenshot": screenshot,
        },
        save_screenshot,
    )


def wait_for_page_to_settle(
    page: Page,
    options: ConsecutiveChecksOptions = {
        "max_timeout_ms": 180000,
        "number_of_checks": 3,
        "percent_difference_threshold": 25,
        "polling_interval_ms": 500,
        "start_time": datetime.now(timezone.utc),
    },
    save_screenshot: bool = False,
) -> None:
    try:
        page.wait_for_load_state("load")
    except Exception as e:
        _LOGGER.debug(f"Failed to wait for page to load. Error: {e}")
        pass
    consecutive_identical_checks(page, options, None, save_screenshot)
