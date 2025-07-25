# Nova Act Samples

This directory contains sample scripts demonstrating how to use the Nova Act library. Each sample provides examples of automation tasks using real websites.

## Sample Overview

### 1. Apartment Search Samples

#### [`apartments_caltrain_walking.py`](./apartments_caltrain_walking.py)
A sample that calculates walking commute time and distance to Caltrain stations.

**Features:**
- Search for apartments on Zumper
- Use Bing Maps to calculate walking distance and time from each apartment to Caltrain station
- Execute distance calculations efficiently using parallel processing
- Display results sorted by commute time in a DataFrame

**Usage:**
```bash
python -m nova_act.samples.apartments_caltrain_walking \
    [--caltrain_city <city_with_caltrain_station>] \
    [--bedrooms <number_of_bedrooms>] \
    [--baths <number_of_baths>] \
    [--headless]
```

#### [`apartments_caltrain.py`](./apartments_caltrain.py)
A sample that calculates biking commute time and distance to Caltrain stations.

**Features:**
- Search for apartments on Zumper
- Use Google Maps to calculate biking distance and time from each apartment to Caltrain station
- Execute distance calculations efficiently using parallel processing
- Display results sorted by commute time in a DataFrame

**Usage:**
```bash
python -m nova_act.samples.apartments_caltrain \
    [--caltrain_city <city_with_caltrain_station>] \
    [--bedrooms <number_of_bedrooms>] \
    [--baths <number_of_baths>] \
    [--headless]
```

#### [`apartments_zumper.py`](./apartments_zumper.py)
A basic sample for searching apartments using Zumper.

**Features:**
- Search for apartments in a specified city
- Filter by number of bedrooms and bathrooms
- Retrieve and display search results in JSON format

**Usage:**
```bash
python -m nova_act.samples.apartments_zumper \
    [--city <city_name>] \
    [--bedrooms <number_of_bedrooms>] \
    [--baths <number_of_baths>] \
    [--headless]
```

### 2. Online Shopping Samples

#### [`order_a_coffee_maker.py`](./order_a_coffee_maker.py)
A simple sample for adding a coffee maker to cart on Amazon.

**Features:**
- Search for coffee makers on Amazon
- Select the first search result
- Add the product to cart
- Optional video recording functionality

**Usage:**
```bash
python -m nova_act.samples.order_a_coffee_maker [--record_video]
```

#### [`order_salad.py`](./order_salad.py)
A sample for ordering salad from Sweetgreen.

**Features:**
- Access Sweetgreen's online ordering site
- Order a specified salad
- Select delivery address, set tip, and complete the order
- Requires a logged-in browser profile

**Prerequisites:**
- user_data_dir logged into order.sweetgreen.com
- Saved credit card and address information

**Usage:**
```bash
python -m nova_act.samples.order_salad \
    --user_data_dir <user_data_directory> \
    [--order <salad_name>] \
    [--headless]
```

### 3. Utility Samples

#### [`s3_writer_example.py`](./s3_writer_example.py)
A sample for uploading session files to AWS S3 using S3Writer.

**Features:**
- Create boto3 session for AWS authentication
- Automatically upload NovaAct session files to S3 using S3Writer
- Save files with metadata
- Optional video recording functionality

**Required AWS Permissions:**
- s3:ListObjects (on bucket and prefix)
- s3:PutObject (on bucket and prefix)

**Usage:**
```bash
python -m nova_act.samples.s3_writer_example \
    <s3_bucket_name> \
    [--s3_prefix <s3_prefix>] \
    [--record_video]
```

#### [`setup_chrome_user_data_dir.py`](./setup_chrome_user_data_dir.py)
A sample for setting up user_data_dir for logged-in websites.

**Features:**
- Create user_data_dir in the specified directory
- Launch browser for manual user login
- Save login information for use in subsequent scripts

**Usage:**
```bash
python -m nova_act.samples.setup_chrome_user_data_dir \
    --user_data_dir <directory_path>
```
