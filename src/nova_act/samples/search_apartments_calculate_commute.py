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
"""Find apartments and calculate distance to transit station.

Shows how to use Nova Act to search for apartments on your favorite real estate platform
and calculate commute times to transit stations on your favorite maps website.

The apartment search occurs synchronously in headed mode and the commute calculation occurs
asynchronously in headless mode to show how to use Nova Act concurrently in a Thread Pool.

Usage:
python -m nova_act.samples.search_apartments_calculate_commute \
    --apartment_url <apartment search website> \
    --maps_url <maps service website> \
    [--transport_mode <walking|biking>] \
    [--transit_city <city_with_a_transit_station>] \
    [--bedrooms <number_of_bedrooms>] \
    [--baths <number_of_baths>] \
    [--headless]
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal, get_args

import fire  # type: ignore
import pandas as pd
from pydantic import BaseModel

from nova_act import NovaAct

TransportMode = Literal["walking", "biking"]
TRANSPORT_MODES = list(get_args(TransportMode))


class Apartment(BaseModel):
    address: str
    price: str
    beds: str
    baths: str


class ApartmentList(BaseModel):
    apartments: list[Apartment]


class TransitCommute(BaseModel):
    commute_time_hours: int
    commute_time_minutes: int
    commute_distance_miles: float


def add_commute_distance(
    apartment: Apartment,
    transit_city: str,
    transport_mode: TransportMode,
    maps_url: str,
) -> TransitCommute | None:
    with NovaAct(
        starting_page=maps_url,
        headless=True,
    ) as nova:
        result = nova.act_get(
            f"Search for {transit_city} transit station and press enter. "
            "Click Directions. "
            f"Enter '{apartment.address}' into the starting point field and press enter. "
            f"Return the shortest {transport_mode} time and distance.",
            schema=TransitCommute.model_json_schema(),
        )
        time_distance = TransitCommute.model_validate(result.parsed_response)
        return time_distance


def main(
    apartment_url: str,
    maps_url: str,
    transit_city: str = "Redwood City",
    transport_mode: TransportMode = "walking",
    bedrooms: int = 2,
    baths: int = 1,
    headless: bool = False,
    min_apartments_to_find: int = 5,
) -> None:
    """Find apartments and calculate distance to transit station.

    Usage:
    python -m nova_act.samples.apartments_transit_walking \
        --apartment_url <apartment search website> \
        --maps_url <maps service website> \
        [--transit_city <city_with_a_transit_station>] \
        [--transport_mode <walking|biking>] \
        [--bedrooms <number_of_bedrooms>] \
        [--baths <number_of_baths>] \
        [--headless]
    """
    if transport_mode not in TRANSPORT_MODES:
        raise ValueError(f"transport_mode must be one of {TRANSPORT_MODES}")

    all_apartments: list[Apartment] = []

    with NovaAct(
        starting_page=apartment_url,
        headless=headless,
    ) as nova:

        nova.act(
            "Close any cookie banners. "
            f"Search for apartments near {transit_city}, "
            f"then filter for {bedrooms} bedrooms and {baths} bathrooms. "
            "Close any dialogs that get in the way of your task. "
            "Ensure the results mode is set to List."
        )

        for _ in range(5):  # Scroll down a max of 5 times.
            result = nova.act_get(
                "Return the currently visible list of apartments",
                schema=ApartmentList.model_json_schema(),
            )
            apartment_list = ApartmentList.model_validate(result.parsed_response)
            all_apartments.extend(apartment_list.apartments)
            if len(all_apartments) >= min_apartments_to_find:
                break
            nova.act("Scroll down once")

        print(f"✓ Found apartments: {all_apartments}")

    apartments_commutable = []
    with ThreadPoolExecutor() as executor:
        future_to_apartment = {
            executor.submit(
                add_commute_distance,
                apartment,
                transit_city,
                transport_mode,
                maps_url,
            ): apartment
            for apartment in all_apartments
        }
        for future in as_completed(future_to_apartment.keys()):
            apartment = future_to_apartment[future]
            commute_details = future.result()
            if commute_details is not None:
                apartments_commutable.append(apartment.model_dump() | commute_details.model_dump())
            else:
                apartments_commutable.append(apartment.model_dump())

    apartments_df = pd.DataFrame(apartments_commutable)
    closest_apartment_data = apartments_df.sort_values(
        by=["commute_time_hours", "commute_time_minutes", "commute_distance_miles"]
    )

    print(f"\n✓ {transport_mode.capitalize()} time and distance:")
    print(f"\n{closest_apartment_data.to_string()}\n")


if __name__ == "__main__":
    fire.Fire(main)
