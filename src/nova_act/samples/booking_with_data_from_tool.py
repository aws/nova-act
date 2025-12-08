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
"""Book a trip.

Shows how to use Nova Act to fill out a multi-step form to book a trip.

Usage:
python -m nova_act.samples.booking_with_data_from_tool
"""

import fire  # type: ignore

from nova_act import NovaAct, tool


@tool
def get_traveller_info() -> dict[str, str]:
    """
    Provides the necessary traveller info to book a flight.
    """
    return {
        "name": "John Doe",
        "date_of_birth": "1/8/2025",
        "emergency_contact_name": "Jane Smith",
        "emergency_contact_relationship": "Spouse",
        "emergency_contact_phone": "555-555-5555",
        "medical_has_traveled_interstellar": "yes",
        "medical_implants": "no",
        "cabin_selection": "premium",
        "additional_cargo": "no",
        "payment_prepaid_code": "NOVAACT2025",
    }


def main() -> None:
    with NovaAct(
        starting_page="https://nova.amazon.com/act/gym/next-dot/booking/step/1", tools=[get_traveller_info]
    ) as nova:
        result = nova.act_get("Book a flight and return the booking number.")
        print(f"✓ Booking number: {result.parsed_response}")


if __name__ == "__main__":
    fire.Fire(main)
