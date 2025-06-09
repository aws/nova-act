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
from concurrent.futures import ThreadPoolExecutor, as_completed

import fire  # type: ignore
import pandas as pd
from pydantic import BaseModel

from nova_act import ActAgentError, NovaAct


class Apartment(BaseModel):
    address: str
    price: str
    beds: str
    baths: str


class ApartmentList(BaseModel):
    apartments: list[Apartment]


class CaltrainCommute(BaseModel):
    commute_time_hours: int
    commute_time_minutes: int
    commute_distance_miles: float


def add_commute_distance(apartment: Apartment, caltrain_city: str, headless: bool) -> CaltrainCommute | None:
    with NovaAct(
        starting_page="https://www.bing.com/maps",
        headless=headless,
    ) as nova:
        try:
            nova.act(
                f"Search for {caltrain_city} Caltrain station and press enter. "
                "Click Directions. "
                f"Enter '{apartment.address}' into the starting point field and press enter. "
                "Click the walking icon for directions."
            )
            result = nova.act("Return the shortest time and distance", schema=CaltrainCommute.model_json_schema())
        except ActAgentError as exc:
            print(f"Could not retrieve walking distance: {exc}")
            return None
        if not result.matches_schema:
            print(f"Invalid JSON while retrieving walking distance {result=}")
            return None
        time_distance = CaltrainCommute.model_validate(result.parsed_response)
        return time_distance


def main(
    caltrain_city: str = "Redwood City",
    bedrooms: int = 2,
    baths: int = 1,
    headless: bool = False,
    min_apartments_to_find: int = 5,
) -> None:
    """Find some apartments and calculate walking distance to Caltrain station.

    Usage:
    python -m nova_act.samples.apartments_caltrain_walking \
        [--caltrain_city <city_with_a_caltrain_station>] \
        [--bedrooms <number_of_bedrooms>] \
        [--baths <number_of_baths>] \
        [--headless]
    """
    all_apartments: list[Apartment] = []

    with NovaAct(
        starting_page="https://zumper.com/",
        headless=headless,
    ) as nova:

        nova.act(
            "Close any cookie banners. "
            f"Search for apartments near {caltrain_city}, CA, "
            f"then filter for {bedrooms} bedrooms and {baths} bathrooms. "
            "If you see a dialog about saving a search, close it. "
            "If results mode is 'Split', switch to 'List'. "
        )

        for _ in range(5):  # Scroll down a max of 5 times.
            result = nova.act(
                "Return the currently visible list of apartments", schema=ApartmentList.model_json_schema()
            )
            if not result.matches_schema:
                print(f"Invalid JSON {result=}")
                break
            apartment_list = ApartmentList.model_validate(result.parsed_response)
            all_apartments.extend(apartment_list.apartments)
            if len(all_apartments) >= min_apartments_to_find:
                break
            nova.act("Scroll down once")

        print(f"Found apartments: {all_apartments}")

    apartments_commutable = []
    with ThreadPoolExecutor() as executor:
        future_to_apartment = {
            executor.submit(add_commute_distance, apartment, caltrain_city, headless): apartment
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

    print()
    print("Commute time and distance:")
    print(closest_apartment_data.to_string())


if __name__ == "__main__":
    fire.Fire(main)
