# Nova Act

A Python SDK for Amazon Nova Act.

Nova Act is an early research preview of an SDK + model for building agents designed to reliably take actions in web browsers. Building with the SDK enables developers to break down complex workflows into smaller, reliable, commands, add more detail where needed, call APIs, and intersperse direct browser manipulation. Developers can interleave Python code, whether it be tests, breakpoints, asserts, or threadpooling for parallelization. Read more about the announcement: https://labs.amazon.science/blog/nova-act.


## Disclosures

Amazon Nova Act is an experimental SDK. When using Nova Act, please keep in mind the following:

1. Nova Act may make mistakes. You are responsible for monitoring Nova Act and using it in accordance with our [Acceptable Use Policy](https://www.amazon.com/gp/help/customer/display.html?nodeId=TTFAPMmEqemeDWZaWf). We collect information on interactions with Nova Act, including prompts and screenshots taken while Nova Act is engaged with the browser, in order to provide, develop, and improve our services. You can request to delete your Nova Act data by emailing us at nova-act@amazon.com.
2. Do not share your API key. Anyone with access to your API key can use it to operate Nova Act under your Amazon account. If you lose your API key or believe someone else may have access to it, contact nova-act@amazon.com to deactivate your key and obtain a new one.
3. We recommend that you do not provide sensitive information to Nova Act, such as account passwords. Note that if you use sensitive information through Playwright calls, the information could be collected in screenshots if it appears unobstructed on the browser when Nova Act is engaged in completing an action. (See [Entering sensitive information](#entering-sensitive-information) below.)
4. If you are using our browsing environment defaults, to identify our agent, look for `NovaAct` in the user agent string. If you operate Nova Act in your own browsing environment or customize the user agent, we recommend that you include that same string.

## Pre-requisites

1. Operating System: MacOS or Ubuntu.
2. Python 3.10 or above.

## Building


```sh
python -m pip install --editable '.[dev]'
python -m build --wheel --no-isolation --outdir dist/ .
```

## Set Up

### Authentication


Navigate to https://nova.amazon.com/act and generate an API key.

To save it as an environment variable, execute in the terminal:
```sh
export NOVA_ACT_API_KEY="your_api_key"
```

### Installation


```bash
pip install nova-act
```

#### [Optional] Install Google Chrome
Nova Act works best with Google Chrome but does not have permission to install this browser. You may skip this step if you already have Google Chrome installed or are fine with using Chromium. Otherwise, you can install Google Chrome by running the following command in the same environment where you installed Nova Act. For more information, visit https://playwright.dev/python/docs/browsers#google-chrome--microsoft-edge.
```bash
playwright install chrome
```


## Quick Start: ordering a coffee maker on Amazon

*Note: The first time you run NovaAct, it may take 1 to 2 minutes to start. This is because NovaAct needs to [install Playwright modules](https://playwright.dev/python/docs/browsers#install-browsers). Subsequent runs will only take a few seconds to start. This functionality can be toggled off by setting the `NOVA_ACT_SKIP_PLAYWRIGHT_INSTALL` environment variable.*

### Script mode

```python
from nova_act import NovaAct

with NovaAct(starting_page="https://www.amazon.com") as nova:
    nova.act("search for a coffee maker")
    nova.act("select the first result")
    nova.act("scroll down or up until you see 'add to cart' and then click 'add to cart'")
```

The SDK will (1) open Chrome, (2) navigate to a coffee maker product detail page on Amazon.com and add it to the cart, and then (3) close Chrome. Details of the run will be printed as console log messages.

Refer to the section [Initializing NovaAct](#initializing-novaact) to learn about other runtime options that can be passed into NovaAct.

### Interactive mode

_**NOTE**: NovaAct does not yet support `ipython`; for now, use your standard Python shell._

Using interactive Python is a nice way to experiment:

```sh
% python
Python 3.10.16 (main, Dec  3 2024, 17:27:57) [Clang 16.0.0 (clang-1600.0.26.4)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>> from nova_act import NovaAct
>>> nova = NovaAct(starting_page="https://www.amazon.com")
>>> nova.start()
>>> nova.act("search for a coffee maker")
```

Once the agent completes the step above, you can enter the next step:

```sh
>>> nova.act("select the first result")
```

Feel free to manipulate the browser in between these `act()` calls as well, but please don't interact with the browser when an `act()` is running because the underlying model will not know what you've changed!

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

with NovaAct(starting_page="https://www.amazon.com") as nova:
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

with NovaAct(starting_page="https://amazon.com/", user_data_dir=user_data_dir, clone_user_data_dir=False) as nova:
    input("Log into your websites, then press enter...")
    # Add your nova.act() statements here.

print(f"User data dir saved to {user_data_dir=}")
```

The script is included in the installation: `python -m nova_act.samples.setup_chrome_user_data_dir`.


### Entering sensitive information

To enter a password or sensitive information (credit card, social security number), do not prompt the model with the sensitive information. Ask the model to focus on the element you want to fill in. Then use Playwright APIs directly to type the data, using `client.page.keyboard.type(sensitive_string)`. You can get that data in the way you wish: prompting in the command line using [`getpass`](https://docs.python.org/3/library/getpass.html), using an argument, or setting env variable.

> **Caution:** If you instruct Nova Act to take an action on any browser screen displaying sensitive information, including information provided through Playwright APIs, that information will be included in the screenshots collected.

```python
# Sign in.
nova.act("enter username janedoe and click on the password field")
# Collect the password from the command line and enter it via playwright. (Does not get sent over the network.)
nova.page.keyboard.type(getpass())
# Now that username and password is filled in, ask NovaAct to proceed.
nova.act("sign in")
```

> **NOTE:** We are aware of an issue where sometimes a page element can not be put into focus by the agent. We are actively working on a fix for this. In the interim, to work around this you can instruct Nova Act in this way:
> ```python
> nova.act("enter '' in the password field")
> nova.page.keyboard.type(getpass())
> ```

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

### Search on a website

```python
nova.go_to_url(website_url)
nova.act("search for cats")
```

If the model has trouble finding the search button, you can instruct it to press enter to initiate the search.

```python
nova.act("search for cats. type enter to initiate the search.")
```

### File download

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

Download the current page (e.g. a pdf) that you have navigated to using `act()`:

```python
# Download the content using Playwright's request.
response = nova.page.request.get(nova.page.url)
with open("downloaded.pdf", "wb") as f:
    f.write(response.body())
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

## Known limitations

Nova Act is a research preview intended for prototyping and exploration. It’s the first step in our vision for building the key capabilities for useful agents at scale. You can expect to encounter many limitations at this stage — please provide feedback to [nova-act@amazon.com](mailto:nova-act@amazon.com?subject=Nova%20Act%20Bug%20Report) to help us make it better.

For example:

* `act()` cannot interact with non-browser applications.
* `act()` is unreliable with high-level prompts.
* `act()` cannot interact with elements hidden behind a mouseover.
* `act()` cannot interact with the browser window. This means that browser modals such as those requesting access to use your location don't interfere with act() but must be manually acknowledged if desired.

## Reference


### Initializing NovaAct

The constructor accepts the following:

* `starting_page (str)`: The URL of the starting page (required argument)
* `headless (bool)`: Whether to launch the browser in headless mode (defaults to `False`)
* `quiet (bool)`: Whether to suppress logs to terminal (defaults to `False`)
* `user_data_dir (str)`: Path to a [user data directory](https://chromium.googlesource.com/chromium/src/+/master/docs/user_data_dir.md#introduction), which stores browser session data like cookies and local storage (defaults to `None`).
* `nova_act_api_key (str)`: The API key you generated for authentication; required if the `NOVA_ACT_API_KEY` environment variable is not set. If passed, takes precedence over the environment variable.
* `logs_directory (str)`: The directory where NovaAct will output its logs, run info, and videos (if `record_video` is set to `True`).
* `record_video (bool))`: Whether to record video and save it to `logs_directory`. Must have `logs_directory` specified for video to record.

This creates one browser session. You can create as many browser sessions as you wish and run them in parallel but a single session must be single-threaded.

### Actuating the browser

#### Use act

`act()` takes a natural language prompt from the user and will actuate on the browser window on behalf of the user to achieve the goal. Arguments:

* `max_steps` (int): Configure the maximum number of steps (browser actuations) `act()` will take before giving up on the task. Use this to make sure the agent doesn't get stuck forever trying different paths. Default is 30.
* `timeout` (int): Number of seconds timeout for the entire act call. Prefer using `max_steps` as time per step can vary based on model server load and website latency.

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

When using interactive mode, ctrl+x can exit the agent action leaving the browser intact for another act() call. ctrl+c does not do this -- it will exit the browser and require a `NovaAct` restart.

#### Do it programmatically

`NovaAct` exposes a Playwright [`Page`](https://playwright.dev/python/docs/api/class-page) object directly under the `page` attribute.

This can be used to retrieve current state of the browser, for example a screenshot or the DOM, or actuate it:

```python
screenshot_bytes = nova.page.screenshot()
dom_string = nova.page.content()
nova.page.keyboard.type("hello")
```

**Caution: Use `nova.go_to_url` instead of `nova.page.goto`**

The Playwright Page's `goto()` method has a default timeout of 30 seconds, which may cause failures for slow-loading websites. If the page does not finish loading within this time, `goto()` will raise a `TimeoutError`, potentially interrupting your workflow. Additionally, goto() does not always work well with act, as Playwright may consider the page ready before it has fully loaded.
To address these issues, we have implemented a new function, `go_to_url()`, which provides more reliable navigation. You can use it by calling: `nova.go_to_url(url)` after `nova.start()`

## Report a Bug
Help us improve! If you notice any issues, please let us know by submitting a bug report via nova-act@amazon.com. 
Be sure to include the following in the email:
- Description of the issue;
- Session ID, which will have been printed out as a console log message;
- Script of the workflow you are using.
	 
Your feedback is valuable in ensuring a better experience for everyone.

Thanks for experimenting with Nova Act!

