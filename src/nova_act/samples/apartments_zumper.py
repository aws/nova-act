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
"""Find some apartments using the provided preferences.

Usage:
python -m nova_act.samples.apartments_zumper \
    [--city <city_name>] \
    [--bedrooms <number_of_bedrooms>] \
    [--baths <number_of_baths>] \
    [--headless]
"""

import fire  # type: ignore
from pydantic import BaseModel

from nova_act import NovaAct


class Apartment(BaseModel):
    address: str
    price: str
    beds: str
    baths: str


class ApartmentList(BaseModel):
    apartments: list[Apartment]


def main(
    city: str = "Redwood City",
    bedrooms: int = 2,
    baths: int = 1,
    headless: bool = False,
    min_apartments_to_find: int = 5,
) -> None:
    all_apartments: list[Apartment] = []

    with NovaAct(
        starting_page="https://zumper.com/",
        headless=headless,
    ) as nova:

        nova.act(
            "Close any cookie banners. "
            f"Search for apartments near {city} "
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


if __name__ == "__main__":
    fire.Fire(main)
