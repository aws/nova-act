# Nova Act

A Python SDK for Amazon Nova Act.

Nova Act is an early research preview of an SDK + model for building agents designed to reliably take actions in web browsers. Building with the SDK enables developers to break down complex workflows into smaller, reliable, commands, add more detail where needed, call APIs, and intersperse direct browser manipulation. Developers can interleave Python code, whether it be tests, breakpoints, asserts, or threadpooling for parallelization. Read more about the announcement: https://labs.amazon.science/blog/nova-act.

>We are now working with select customers to productionize their agents, with capabilities including [AWS IAM authentication](https://aws.amazon.com/iam/), [Amazon S3](https://aws.amazon.com/s3/) secure storage, and integration with the [Amazon Bedrock AgentCore Browser](https://aws.amazon.com/bedrock/agentcore). Learn more in our [blog post](https://labs.amazon.science/blog/prototype-to-production) and join our [waitlist](https://amazonexteu.qualtrics.com/jfe/form/SV_9siTXCFdKHpdwCa).


## Disclosures

Amazon Nova Act is an experimental SDK. When using Nova Act, please keep in mind the following:

1. ⚠️ Please be aware that Nova Act may encounter commands in the content it encounters on third party websites. These unauthorized commands, known as prompt injections, may cause the model to make mistakes or act in a manner that differs from user-provided or model instructions. To reduce the risks associated with prompt injections, it is important to monitor Nova Act and limit its operations to websites you trust.
2. Nova Act may make mistakes. You are responsible for monitoring Nova Act and using it in accordance with our [Acceptable Use Policy](https://www.amazon.com/gp/help/customer/display.html?nodeId=TTFAPMmEqemeDWZaWf). When using the research preview, we collect information on interactions with Nova Act, including prompts and screenshots taken while Nova Act is engaged with the browser, in order to provide, develop, and improve our services. You can request to delete your Nova Act data by emailing us at nova-act@amazon.com.
3. Do not share your API key. Anyone with access to your API key can use it to operate Nova Act under your Amazon account. If you lose your API key or believe someone else may have access to it, go to https://nova.amazon.com/act to deactivate your key and obtain a new one.
4. We recommend that you do not provide sensitive information to Nova Act, such as account passwords. Note that if you use sensitive information through Playwright calls, the information could be collected in screenshots if it appears unobstructed on the browser when Nova Act is engaged in completing an action. (See [Entering sensitive information](#entering-sensitive-information) below.).
5. If you are using our browsing environment defaults, to identify our agent, look for `NovaAct` in the user agent string. If you operate Nova Act in your own browsing environment or customize the user agent, we recommend that you include that same string.

## Table of contents
* [Pre-requisites](#pre-requisites)
* [Nova Act Authentication and Installation](#set-up)
* [Quick Start](#quick-start)
* [How to prompt Nova Act](#how-to-prompt-act)
* [Extract information from a web page](#extracting-information-from-a-web-page)
* [Run multiple sessions in parallel](#running-multiple-sessions-in-parallel)
* [Authentication, cookies, and persisting browser state](#authentication-cookies-and-persistent-browser-state)
* [Handling sensitive data](#entering-sensitive-information)
* [Captchas](#captchas)
* [Search on a website](#search-on-a-website)
* [File upload and download](#file-upload-and-download)
* [Working with dates](#picking-dates)
* [Setting the browser user agent](#setting-the-browser-user-agent)
* [Using a proxy](#using-a-proxy)
* [Logging and viewing traces](#logging)
* [Recording a video of a session](#recording-a-session)
* [Storing Session Data in Amazon S3](#storing-session-data-in-your-amazon-s3-bucket)
* [Navigating Pages](#navigating-pages)
* [Viewing headless sessions](#viewing-a-session-that-is-running-in-headless-mode)
* [Use Nova Act SDK with Amazon Bedrock AgentCore Browser Tool](#use-nova-act-sdk-with-amazon-bedrock-agentcore-browser-tool)
* [Known limitations](#known-limitations)
* [Reference: Nova Act constructor parameters](#initializing-novaact)
* [Reference: Actuating the browser](#actuating-the-browser)

## Pre-requisites

1. Operating System: MacOS Sierra+, Ubuntu 22.04+, WSL2 or Windows 10+
2. Python: 3.10 or above

> **Note:** Nova Act supports English.

## Set Up

### Authentication

#### API Key Authentication


Navigate to https://nova.amazon.com/act and generate an API key.

To save it as an environment variable, execute in the terminal:
```sh
export NOVA_ACT_API_KEY="your_api_key"
```


### Installation

```bash
pip install nova-act
```


Alternatively, you can build `nova-act`. Clone this repo, and then:
```sh
pip install .
```

#### [Optional] Install Google Chrome
Nova Act works best with Google Chrome but does not have permission to install this browser. You may skip this step if you already have Google Chrome installed or are fine with using Chromium. Otherwise, you can install Google Chrome by running the following command in the same environment where you installed Nova Act. For more information, visit https://playwright.dev/python/docs/browsers#google-chrome--microsoft-edge.
```bash
playwright install chrome
```


## Quick Start

*Note: The first time you run NovaAct, it may take 1 to 2 minutes to start. This is because NovaAct needs to [install Playwright modules](https://playwright.dev/python/docs/browsers#install-browsers). Subsequent runs will only take a few seconds to start. This functionality can be toggled off by setting the `NOVA_ACT_SKIP_PLAYWRIGHT_INSTALL` environment variable.*

### Script mode

```python
from nova_act import NovaAct

with NovaAct(starting_page="https://nova.amazon.com/act") as nova:
    nova.act("Click learn more. Then, return the title and publication date of the blog.")
```

The SDK will (1) open Chrome, (2) perform the task as described in the prompt, and then (3) close Chrome. Details of the run will be printed as console log messages.

Refer to the section [Initializing NovaAct](#initializing-novaact) to learn about other runtime options that can be passed into NovaAct.

### Interactive mode

_**NOTE**: NovaAct does not yet support `ipython`; for now, use your standard Python shell._

Using interactive Python is a nice way to experiment:

```sh
% python
Python 3.10.16 (main, Dec  3 2024, 17:27:57) [Clang 16.0.0 (clang-1600.0.26.4)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>> from nova_act import NovaAct
>>> nova = NovaAct(starting_page="https://nova.amazon.com/act")
>>> nova.start()
>>> nova.act("Click learn more. Then, return the title and publication date of the blog.")
```

Feel free to manipulate the browser in between these `act()` calls as well, but please don't interact with the browser when an `act()` is running because the underlying model will not know what you've changed!

> Note: When using interactive mode, `ctrl+x` can exit the agent action leaving the browser intact for another `act()` call. `ctrl+c` does not do this -- it will exit the browser and require a `NovaAct` restart.


### Samples

The [samples](./src/nova_act/samples) folder contains several examples of using Nova Act to complete various tasks, including:
* search for apartments on a real estate website, search for each apartment's distance from a train station, and combine these into a single result set. [This sample](./src/nova_act/samples/apartments_caltrain.py) demonstrates running multiple NovaActs in parallel (more detail below).
* order a meal from Sweetgreen and have it delivered. [This sample](./src/nova_act/samples/order_salad.py) demonstrates how to override the `user_data_dir` to provide a browser that is authenticated to order.sweetgreen.com (more detail below).

## How to prompt act()

Existing computer-use agents attempt to accomplish an end-to-end task by specifying the entire goal, possibly with hints to guide the agent, in one prompt. The agent then must take many steps sequentially to achieve the goal, and any issues or nondeterminism along the way can throw the workflow off track.

Unfortunately, the current SOTA agent models are unable to achieve a satisfactory level of reliability when used this way. With Nova Act, we suggest breaking up the steps in the prompt to multiple `act()` calls as if you were telling another person how to complete a task. We believe this is the current best route for building repeatable, reliable, easy to maintain workflows.

When prompting Nova Act:

**1. Be prescriptive and succinct in what the agent should do**

❌ DON'T
```python
nova.act("From my order history, find my most recent order from India Palace and reorder it")
```

✅ DO
```python
nova.act("Click the hamburger menu icon, go to Order History, find my most recent order from India Palace and reorder it")
```

❌ DON'T
```python
nova.act("Let's see what routes vta offers")
```

✅ DO
```python
nova.act("Navigate to the routes tab")
```

❌ DON'T
```python
nova.act("I want to go and meet a friend. I should figure out when the Orange Line comes next.")
```

✅ DO
```python
nova.act(f"Find the next departure time for the Orange Line from Government Center after {time}")
```

**2. Break up large acts into smaller ones**

❌ DON'T
```python
nova.act("book me a hotel that costs less than $100 with the highest star rating")
```

✅ DO
```python
nova.act(f"search for hotels in Houston between {startdate} and {enddate}")
nova.act("sort by avg customer review")
nova.act("hit book on the first hotel that is $100 or less")
nova.act(f"fill in my name, address, and DOB according to {blob}")
...
```

## Common Building Blocks

### Extracting information from a web page

Use `pydantic` and ask `act()` to respond to a question about the browser page in a certain schema.

- Make sure you use a schema whenever you are expecting any kind of structured response, even just a bool (yes/no).
- Put a prompt to extract information in its own separate `act()` call.

Example:
```python
from pydantic import BaseModel
from nova_act import NovaAct, ActResult


class Book(BaseModel):
    title: str
    author: str

class BookList(BaseModel):
    books: list[Book]


def get_books(year: int) -> BookList | None:
    """
    Get top NYT top books of the year and return as a BookList. Return None if there is an error.
    """
    with NovaAct(
        starting_page=f"https://en.wikipedia.org/wiki/List_of_The_New_York_Times_number-one_books_of_{year}#Fiction"
    ) as nova:
        result = nova.act("Return the books in the Fiction list",
                       # Specify the schema for parsing.
                       schema=BookList.model_json_schema())
        if not result.matches_schema:
            # act response did not match the schema ¯\_(ツ)_/¯
            return None
        # Parse the JSON into the pydantic model.
        book_list = BookList.model_validate(result.parsed_response)
        return book_list
```

If all you need is a bool response, there's a convenient `BOOL_SCHEMA` constant:

Example:
```python
from nova_act import NovaAct, BOOL_SCHEMA

with NovaAct(starting_page="https://nova.amazon.com/act") as nova:
    result = nova.act("Am I logged in?", schema=BOOL_SCHEMA)
    if not result.matches_schema:
        # act response did not match the schema ¯\_(ツ)_/¯
        print(f"Invalid result: {result=}")
    else:
        # result.parsed_response is now a bool
        if result.parsed_response:
            print("You are logged in")
        else:
            print("You are not logged in")
```

### Running multiple sessions in parallel

One `NovaAct` instance can only actuate one browser at a time. However, it is possible to actuate multiple browsers concurrently with multiple `NovaAct` instances! They are quite lightweight. You can use this to parallelize parts of your task, creating a kind of browser use map-reduce for the internet. The following will search for books in parallel across different browser instances. Note, the below code builds on the books sample in the previous "Extracting information from a web page" section.

Using the `get_books` example above:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

from nova_act import ActError, NovaAct


# Accumulate the complete list here.
all_books = []
# Set max workers to the max number of active browser sessions.
with ThreadPoolExecutor(max_workers=10) as executor:
    # Get all books from years 2010 to 2024 in parallel.
    future_to_books = {
        executor.submit(get_books, year): year for year in range(2010, 2025)
    }
    # Collect the results in ot all_books.
    for future in as_completed(future_to_books.keys()):
        try:
            year = future_to_books[future]
            book_list = future.result()
            if book_list is not None:
                all_books.extend(book_list.books)
        except ActError as exc:
            print(f"Skipping year due to error: {exc}")

print(f"Found {len(all_books)} books:\n{all_books}")
```

### Authentication, cookies, and persistent browser state

Nova Act supports working with authenticated browser sessions by overriding its default settings. By default, when Nova Act runs, it clones the Chromium user data directory and deletes it at the end of the run. To use authenticated sessions, you need to specify an existing directory containing the authenticated sessions, and disable the cloning (which in turn disables deletion of the directory).

Specifically, you need to:
1. (optional) Create a new local directory for the user data directory For example, `/tmp/user-data-dir`. You can skip this step to use an existing Chromium profile.
2. specify this directory when instantiating `NovaAct` via the `user_data_dir` parameter
3. disable cloning this directory when instantiating `NovaAct` by passing in the parameter `clone_user_data_dir=False`
4. instruct Nova Act to open the site(s) into which you want to authenticate
5. authenticate into the sites. See [Entering sensitive information](#entering-sensitive-information) below for more information on entering sensitive data
6. stop your Nova Act session

The next time you run Nova Act with `user_data_dir` set to the directory you created in step 1, you will start from an authenticated session. In subsequent runs, you can decide if you want to enable or disable cloning. If you are running multiple `NovaAct` instances in parallel, they must each create their own copy so you must enable cloning in that use case (`clone_user_data_dir=True`).

Here's an example script that shows how to pass in these parameters.

```python
import os

from nova_act import NovaAct

os.makedirs(user_data_dir, exist_ok=True)

with NovaAct(starting_page="https://nova.amazon.com/act", user_data_dir=user_data_dir, clone_user_data_dir=False) as nova:
    input("Log into your websites, then press enter...")
    # Add your nova.act() statements here.

print(f"User data dir saved to {user_data_dir=}")
```

The script is included in the installation: `python -m nova_act.samples.setup_chrome_user_data_dir`.

#### Run against the local default Chrome browser

If your local default Chrome browser has extensions or security features you need for sites you need your workflow to access, you can configure the SDK to use the Chrome browser installed on your machine rather than the one managed by the SDK using the `NovaAct` parameters below.

> **Important notes:**
> 
> - This feature currently only works for MacOS
> - This will quit your default running Chrome and restart it with new arguments. At the end of the session, it will quit Chrome.
> - If your Chrome browser has many tabs open, consider closing unnecessary ones before running the automation, as Chrome's performance during the restart can be affected by high numbers of open tabs.

Before starting NovaAct with this feature, you must copy the files from your system Chrome user_data_dir to a location of your choice. 
This is necessary as Chrome does not allow CDP connections into instances started with the system default user_data_dir.

Manually, this is can be done with:
```
rsync -a --exclude="Singleton*" /Users/$USER/Library/Application\ Support/Google/Chrome/ <your choice of location>
```
You can also use the convenience function `rsync_from_default_user_data(<your choice of location>)` to create and update that directory as part of your script.
Note that invoking `rsync_from_default_user_data` will overwrite changes in the destination directory and make it an exact mirror of `/Users/$USER/Library/Application\ Support/Google/Chrome/` by overwriting existing files with the same name as in the source and deleting files not in it. If you want to persist profile changes that NovaAct made in the working directory back to your system, you must then mirror the changes back into the system default dir with your own implementation after stopping NovaAct.

When using this feature, you must specify `clone_user_data_dir=False` and pass the desired working dir as `user_data_dir` with the appropriate files populated. This is because `NovaAct` will not be cloning or deleting the `user_data_dir`s for you in this mode.

```python
>>> from nova_act import NovaAct, rsync_from_default_user_data
>>> working_user_data_dir = "/Users/$USER/your_choice_of_path"
>>> rsync_from_default_user_data(working_user_data_dir)
>>> nova = NovaAct(use_default_chrome_browser=True, clone_user_data_dir=False, user_data_dir=working_user_data_dir, starting_page="https://nova.amazon.com/act")
>>> nova.start()
>>> nova.act("Click learn more. Then, return the title and publication date of the blog.")
...
>>> nova.stop()
>>> quit()
```

### Entering sensitive information

To enter a password or sensitive information (credit card, social security number), do not prompt the model with the sensitive information. Ask the model to focus on the element you want to fill in. Then use Playwright APIs directly to type the data, using `client.page.keyboard.type(sensitive_string)`. You can get that data in the way you wish: prompting in the command line using [`getpass`](https://docs.python.org/3/library/getpass.html), using an argument, or setting env variable.

Note that any passwords or other sensitive data saved with a Chromium-based browser's password manager on Linux systems without a system-level keyring (ex. Libsecret, KWallet) will be stored in plaintext within a user's profile directory.

> **Caution:** If you instruct Nova Act to take an action on any browser screen displaying sensitive information, including information provided through Playwright APIs, that information will be included in the screenshots collected.

```python
# Sign in.
nova.act("enter username janedoe and click on the password field")
# Collect the password from the command line and enter it via playwright. (Does not get sent over the network.)
nova.page.keyboard.type(getpass())
# Now that username and password is filled in, ask NovaAct to proceed.
nova.act("sign in")
```

### Captchas

NovaAct will not solve captchas. It is up to the user to do that. If your script encounters captchas in certain places, you can do the following:

1. Check if a captcha is being presented (by using `act()` to inspect the screen)
2. If so, pause the workflow and ask the user to get past the captcha, e.g. using `input()` for a workflow launched from a terminal, and then let the user resume once the flow is past the captcha.

```python
result = nova.act("Is there a captcha on the screen?", schema=BOOL_SCHEMA)
if result.matches_schema and result.parsed_response:
    input("Please solve the captcha and hit return when done")
...
```

Please refer to the section below on [headless browsing](#viewing-a-session-that-is-running-in-headless-mode) to see how to handle captchas when running Nova Act in headless mode and in the cloud.

### Search on a website

```python
nova.go_to_url(website_url)
nova.act("search for cats")
```

If the model has trouble finding the search button, you can instruct it to press enter to initiate the search.

```python
nova.act("search for cats. type enter to initiate the search.")
```

### File upload and download

You can use playwright to download a file on a web page.

Through a download action button:

```python
# Ask playwright to capture any downloads, then actuate the page to initiate it.
with nova.page.expect_download() as download_info:
    nova.act("click on the download button")

# Temp path for the download is available.
print(f"Downloaded file {download_info.value.path()}")

# Now save the downloaded file permanently to a location of your choice.
download_info.value.save_as("my_downloaded_file")
```

> **Important notes**:
>
> - The browser will show the file being downloaded to the temporary path defined by Playwright ([see docs](https://playwright.dev/docs/downloads#introduction))
>    - This temporary path is accessible via `download_info.value.path()`
>  - When using `download_info.value.save_as()`:
>    - If a full path is provided (e.g., "/path/to/my_downloaded_file"), the file will be saved there
>    - If only a filename is provided (e.g., "my_downloaded_file"), it will be saved in the current working directory where the Python script was executed from

To download the current page:

1. If it's HTML, then accessing `nova.page.content()` will give you the rendered DOM. You can save that to a file.
2. If it is another content type, like a pdf, you can download it using `nova.page.request`:

```python
# Download the content using Playwright's request.
response = nova.page.request.get(nova.page.url)
with open("downloaded.pdf", "wb") as f:
    f.write(response.body())
```

To upload a file on a site that uses the `file` `input` type, you can use Playwright's `set_input_files` facility. For a page with a single file upload affordance, the following sample will work but if you need to select among multiple input elements, please see Playwright documentation.

```python
# This starts the upload but does not block on its completion.
nova.page.set_input_files('input[type="file"]', upload_filename)

# Use act to wait for the upload completion. MODIFY THIS TO MATCH THE UPLOAD INDICATOR ON YOUR SITE.
nova.act("wait for the upload spinner to finish")
```

### Picking dates

Specifying the start and end dates in absolute time works best.

```python
nova.act("select dates march 23 to march 28")
```

### Setting the browser user agent

Nova Act comes with Playwright's Chrome and Chromium browsers. These use the default User Agent set by Playwright. You can override this with the `user_agent` option:

```python
nova = NovaAct(..., user_agent="MyUserAgent/2.7")
```

### Using a proxy

Nova Act supports proxy configurations for browser sessions. This can be useful when you need to route traffic through a specific proxy server:

```python
# Basic proxy without authentication
proxy_config = {
    "server": "http://proxy.example.com:8080"
}

# Proxy with authentication
proxy_config = {
    "server": "http://proxy.example.com:8080",
    "username": "myusername",
    "password": "mypassword"
}

nova = NovaAct(
    starting_page="https://example.com",
    proxy=proxy_config
)
```

> **Note:** Proxy configuration is not supported when connecting to a CDP endpoint or when using the default Chrome browser (`use_default_chrome_browser=True`).

### Logging

By default, `NovaAct` will emit all logs level `logging.INFO` or above. This can be overridden by specifying an integer value under the `NOVA_ACT_LOG_LEVEL` environment variable. Integers should correspond to [Python logging levels](https://docs.python.org/3/library/logging.html#logging-levels).
 
### Viewing act traces
 
After an `act()` finishes, it will output traces of what it did in a self-contained html file. The location of the file is printed in the console trace.
 
```sh
> ** View your act run here: /var/folders/6k/75j3vkvs62z0lrz5bgcwq0gw0000gq/T/tmpk7_23qte_nova_act_logs/15d2a29f-a495-42fb-96c5-0fdd0295d337/act_844b076b-be57-4014-b4d8-6abed1ac7a5e_output.html
```
 
You can change the directory for this by passing in a `logs_directory` argument to `NovaAct`.

### Recording a session
 
You can record an entire browser session easily by setting the `logs_directory` and specifying `record_video=True` in the constructor for `NovaAct`.

### Storing Session Data in Your Amazon S3 Bucket

Nova Act allows you to store session data (HTML traces, screenshots, etc.) in your own [Amazon S3](https://aws.amazon.com/s3/) bucket using the `S3Writer` convenience utility:

```python
import boto3
from nova_act import NovaAct
from nova_act.util.s3_writer import S3Writer

# Create a boto3 session with appropriate credentials
boto_session = boto3.Session()

# Create an S3Writer
s3_writer = S3Writer(
    boto_session=boto_session,
    s3_bucket_name="my-bucket",
    s3_prefix="my-prefix/",  # Optional
    metadata={"Project": "MyProject"}  # Optional
)

# Use the S3Writer with NovaAct
with NovaAct(
    starting_page="https://nova.amazon.com/act",
    boto_session=boto_session,  # You may use API key here instead
    stop_hooks=[s3_writer]
) as nova:
    nova.act("Click learn more. Then, return the title and publication date of the blog.")
```

The S3Writer requires the following AWS permissions:
- s3:ListObjects on the bucket and prefix
- s3:PutObject on the bucket and prefix

When the NovaAct session ends, all session files will be automatically uploaded to the specified S3 bucket with the provided prefix.

#### S3 Upload Troubleshooting

**No files in S3 bucket?**
- Check logs for "Registered stop hooks" message during initialization
- Verify your code path actually executes the NovaAct context manager

### Navigating pages

> **Use `nova.go_to_url` instead of `nova.page.goto`**

The Playwright Page's `goto()` method has a default timeout of 30 seconds, which may cause failures for slow-loading websites. If the page does not finish loading within this time, `goto()` will raise a `TimeoutError`, potentially interrupting your workflow. Additionally, goto() does not always work well with act, as Playwright may consider the page ready before it has fully loaded.
To address these issues, we have implemented a new function, `go_to_url()`, which provides more reliable navigation. You can use it by calling: `nova.go_to_url(url)` after `nova.start()`. You can also use the `go_to_url_timeout` parameter on `NovaAct` initialization to modify the default max wait time in seconds for the start page load and subsequent `got_to_url()` calls.

### Viewing a session that is running in headless mode

When running the browser in headless mode (`headless: True`), you may need to see how the workflow is progressing as the agent is going through it. To do this:
1. set the following environment variables before starting your Nova Act workflow
```bash
export NOVA_ACT_BROWSER_ARGS="--remote-debugging-port=9222"
```
2. start your Nova Act workflow as you normally do, with `headless: True`
3. Open a local browser to `http://localhost:9222/json`
4. Look for the item of type `page` and copy and paste its `devtoolsFrontendUrl` into the browser

You'll now be observing the activity happening within the headless browser. You can also interact with the browser window as you normally would, which can be helpful for handling captchas. For example, in your Python script:
1. ask Nova Act to check if there is a captcha
2. if there is, `sleep()` for a period of time. Loop back to step 1. During `sleep()`...
3. send an email / SMS alert (eg, with [Amazon Simple Notification Service](https://aws.amazon.com/sns/)) containing the `devtoolsFrontendUrl` signaling human intervention is required
4. a human opens the `devtoolsFrontendUrl` and solves the captcha
5. the next time step 1 is run, Nova Act will see the captcha has been solved, and the script will continue

Note that if you are running Nova Act on a remote host, you may need to set up port forwarding to enable access from another system.


## Use Nova Act SDK with Amazon Bedrock AgentCore Browser Tool

The Nova Act SDK can be used together with the [Amazon Bedrock AgentCore Browser Tool](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html) for production-ready browser automation at scale. The AgentCore Browser Tool provides a fully managed cloud-based browser automation solution that addresses limitations around real-time data access, while the Nova Act SDK gives you the flexibility to build sophisticated agent workflows.

See [this blog post](https://aws.amazon.com/blogs/machine-learning/introducing-amazon-bedrock-agentcore-browser-tool/) for integration instructions.

## Known limitations
Nova Act is a research preview intended for prototyping and exploration. It’s the first step in our vision for building the key capabilities for useful agents at scale. You can expect to encounter many limitations at this stage — please provide feedback to [nova-act@amazon.com](mailto:nova-act@amazon.com?subject=Nova%20Act%20Bug%20Report) to help us make it better.

For example:

* `act()` cannot interact with non-browser applications.
* `act()` is unreliable with high-level prompts.
* `act()` cannot interact with elements hidden behind a mouseover.
* `act()` cannot interact with the browser window. This means that browser modals such as those requesting access to use your location don't interfere with act() but must be manually acknowledged if desired.
* `act()` is not yet optimized for PDF file actuation.
* Screen size constraints
  * Nova Act is optimized for resolutions between `864×1296` and `1536×2304`
  * Performance may degrade outside this range

## Reference


### Initializing `NovaAct`

The constructor accepts the following:

* `starting_page (str)`: The URL of the starting page; supports both web URLs (`https://`) and local file URLs (`file://`) (required argument)
  * Note: file URLs require passing `ignore_https_errors=True` to the constructor
* `headless (bool)`: Whether to launch the browser in headless mode (defaults to `False`)
* `quiet (bool)`: Whether to suppress logs to terminal (defaults to `False`)
* `user_data_dir (str)`: Path to a [user data directory](https://chromium.googlesource.com/chromium/src/+/master/docs/user_data_dir.md#introduction), which stores browser session data like cookies and local storage (defaults to `None`).
* `nova_act_api_key (str)`: The API key you generated for authentication; required if the `NOVA_ACT_API_KEY` environment variable is not set. If passed, takes precedence over the environment variable.
* `logs_directory (str)`: The directory where NovaAct will output its logs, run info, and videos (if `record_video` is set to `True`).
* `record_video (bool))`: Whether to record video and save it to `logs_directory`. Must have `logs_directory` specified for video to record.
* `proxy (dict)`: Proxy configuration for the browser. Should be a dictionary containing:
  * `server` (required): The proxy server URL (must start with `http://` or `https://`)
  * `username` (optional): Username for proxy authentication
  * `password` (optional): Password for proxy authentication
  * Note: Proxy is not supported when connecting to a CDP endpoint or using the default Chrome browser

This creates one browser session. You can create as many browser sessions as you wish and run them in parallel but a single session must be single-threaded.

### Actuating the browser

#### Use act

`act()` takes a natural language prompt from the user and will actuate on the browser window on behalf of the user to achieve the goal. Arguments:

* `max_steps` (int): Configure the maximum number of steps (browser actuations) `act()` will take before giving up on the task. Use this to make sure the agent doesn't get stuck forever trying different paths. Default is 30.
* `timeout` (int): Number of seconds timeout for the entire act call. Prefer using `max_steps` as time per step can vary based on model server load and website latency.
* `observation_delay_ms`: Additional delay in milliseconds before taking an observation of the page. Useful to wait for UI animations to complete.

Returns an `ActResult`.

```python
class ActResult:
    response: str | None
    parsed_response: Union[Dict[str, Any], List[Any], str, int, float, bool] | None
    valid_json: bool | None
    matches_schema: bool | None
    metadata: ActMetadata

class ActMetadata:
    session_id: str | None
    act_id: str | None
    num_steps_executed: int
    start_time: float
    end_time: float
    prompt: string
```

#### Do it programmatically

`NovaAct` exposes a Playwright [`Page`](https://playwright.dev/python/docs/api/class-page) object directly under the `page` attribute.

This can be used to retrieve current state of the browser, for example a screenshot or the DOM, or actuate it:

```python
screenshot_bytes = nova.page.screenshot()
dom_string = nova.page.content()
nova.page.keyboard.type("hello")
```

## Report a Bug
Help us improve! If you notice any issues, please let us know by submitting a bug report via nova-act@amazon.com. 
Be sure to include the following in the email:
- Description of the issue;
- Session ID, which will have been printed out as a console log message;
- Script of the workflow you are using.
	 
Your feedback is valuable in ensuring a better experience for everyone.

Thanks for experimenting with Nova Act!

