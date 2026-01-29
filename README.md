# Nova Act SDK

A Python SDK for Amazon Nova Act.

Amazon Nova Act is available as a new AWS service to build and manage fleets of reliable AI agents for automating production UI workflows at scale. Nova Act completes repetitive UI workflows in the browser and escalates to a human supervisor when appropriate. You can define workflows by combining the flexibility of natural language with Python code. Start by exploring in the web playground at nova.amazon.com/act, develop and debug in your IDE, deploy to AWS, and monitor your workflows in the AWS Console, all in just a few steps.

(Preview) Nova Act also integrates with external tools through API calls, remote MCP, or agentic frameworks, such as Strands Agents.


> #### ⚠️ Important: Nova Act SDK versions older than 3.0 are no longer supported. Users must upgrade to the latest version to receive security updates and new features.

> Please follow the upgrade instructions below:

 > ```bash
 > # Upgrade to the latest version
 > pip install --upgrade nova-act
 >
 > # Check your current version
 > pip show nova-act
 > ```

## Table of contents
* [Pre-requisites](#pre-requisites)
* [Nova Act IDE Extension](#quick-set-up-with-ide-extension)
* [Nova Act Authentication and Installation](#authentication)
* [Quick Start](#quick-start)
* [How to prompt Nova Act](#how-to-prompt-act)
* [Workflows](#workflows)
* [Extract information from a web page](#extracting-information-from-a-web-page)
* [Human-in-the-loop (HITL)](#human-in-the-loop-hitl) 
* [Tools](#tool-use-beyond-the-browser-preview)
* [Run multiple sessions in parallel](#running-multiple-sessions-in-parallel)
* [Authentication, cookies, and persisting browser state](#authentication-cookies-and-persistent-browser-state)
* [Handling sensitive data](#entering-sensitive-information)
* [Captchas](#captchas)
* [Search on a website](#search-on-a-website)
* [File upload and download](#file-upload-and-download)
* [Working with Browser Dialogs](#working-with-browser-dialogs)
* [Working with dates](#picking-dates)
* [Setting the browser user agent](#setting-the-browser-user-agent)
* [Using a proxy](#using-a-proxy)
* [Time worked tracking utility](#time-worked-tracking-utility)
* [Logging and viewing traces](#logging)
* [Recording a video of a session](#recording-a-session)
* [Storing Session Data in Amazon S3](#storing-session-data-in-your-amazon-s3-bucket)
* [Navigating Pages](#navigating-pages)
* [Viewing headless sessions](#viewing-a-session-that-is-running-in-headless-mode)
* [Use Nova Act SDK with Amazon Bedrock AgentCore Browser Tool](#use-nova-act-sdk-with-amazon-bedrock-agentcore-browser-tool)
* [Known limitations](#known-limitations)
* [Disclosures](#disclosures)
* [Report a Bug](#report-a-bug)
* [Reference: Nova Act constructor parameters](#initializing-novaact)
* [Reference: Actuating the browser](#actuating-the-browser)
* [Reference: Nova Act CLI](#nova-act-cli)

## Pre-requisites

1. Operating System: MacOS Sierra+, Ubuntu 22.04+, WSL2 or Windows 10+
2. Python: 3.10 or above

> **Note:** Nova Act supports English.

## Set Up

### Quick Set Up with IDE Extension

Accelerate your development process with the [Nova Act extension](https://github.com/aws/nova-act-extension). The extension automates the setup of your Nova Act development environment and brings the entire agent development experience directly into your IDE, enabling chat-to-script generation, browser session debugging, and step-by-step testing capabilities. For installation instructions and detailed documentation, visit the [extension repository](https://github.com/aws/nova-act-extension) or [website](https://nova.amazon.com/act).

### Authentication

#### API Key Authentication

Note: When using the Nova Act Playground and/or choosing Nova Act developer tools with API key authentication, access and use are subject to the nova.amazon.com Terms of Use. 


Navigate to https://nova.amazon.com/act and generate an API key.

To save it as an environment variable, execute in the terminal:
```sh
export NOVA_ACT_API_KEY="your_api_key"
```

#### IAM-based Authentication

Note: When choosing developer tools with AWS IAM authentication and/or deploying workflows to the Nova Act AWS service, your AWS Service Terms and/or Customer Agreement (or other agreement governing your use of the AWS Service) apply.

Nova Act also supports authentication using IAM credentials. For details please refer to the Amazon [Nova Act User Guide documentation](https://docs.aws.amazon.com/nova-act/latest/userguide/). To use IAM-based credentials use the Workflow constructs (see [Worfklows](#workflows)). Please note the SDK will instantiate a default boto session if AWS credentials are already configured in your environment.

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

with NovaAct(starting_page="https://nova.amazon.com/act/gym/next-dot/search") as nova:
    nova.act("Find flights from Boston to Wolf on Feb 22nd")
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
>>> nova = NovaAct(starting_page="https://nova.amazon.com/act/gym/next-dot/search")
>>> nova.start()
>>> nova.act("Find flights from Boston to Wolf on Feb 22nd")
```

Please don't interact with the browser when an `act()` is running because the underlying model will not know what you've changed!
> Note: When using interactive mode, `ctrl+x` can exit the agent action leaving the browser intact for another `act()` call. `ctrl+c` does not do this -- it will exit the browser and require a `NovaAct` restart.

### Samples

The [samples](./src/nova_act/samples) folder contains several examples of using Nova Act to complete various tasks, including:
* search for apartments on a real estate website, find each apartment's distance from a train station using a maps website, and combine these into a single result set. [This sample](./src/nova_act/samples/search_apartments_calculate_commute.py) demonstrates running multiple NovaActs in parallel (more detail below).
* book a flight using data that is provided by a tool, and return the booking number. [This sample](./src/nova_act/samples/booking_with_data_from_tool.py) demonstrates how to implement a python function as a tool that can be used to provide data for the workflow.
* allows a human to log into an email application, and approve to print the number of emails. [This sample](./src/nova_act/samples/print_number_of_emails.py) demonstrates providing HITL (Human in the loop) callback implementations to incorporate human participation in the workflow.

For more samples showing how to use Nova Act SDK, please refer to this [Github repository](https://github.com/amazon-agi-labs/nova-act-samples)

## How to prompt act()

The simplest way to use Nova Act to achieve an end-to-end task is by specifying the entire goal, possibly with hints to guide the agent, in one prompt. However, the agent then must take many steps sequentially to achieve the goal, and any issues or nondeterminism along the way can throw the workflow off track. We have found that Nova Act works most reliably when the task can be accomplished in fewer than 30 steps.

Make sure the prompt is direct and spells out exactly what you want Nova Act to do, including what information you want it to return, if any (read more on data extraction [here](#extracting-information-from-a-web-page)). Aim to completely specify the choices the agent should make and what values it should put in form fields. During your testing, if you see act() going off track, enhance the prompt with hints (e.g. how to use certain UI elements it encounters, how to get to a particular function on the website, or what paths to avoid) — just like you would do with a new team member who might be unfamiliar with the task and the website. If the agent is taking a long winding path or you are unable to get repeated reliability, break the task up into stages and connect these in code.

**1. Be direct and succinct in what the agent should do**

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
nova.act_get("I want to go and meet a friend. I should figure out when the Orange Line comes next.")
```

✅ DO
```python
nova.act_get(f"Find the next departure time for the Orange Line from Government Center after {time}")
```

**2. Provide complete instructions**

❌ DON'T
```python
nova.act("book me a hotel that costs less than $100 with the highest star rating")
```

✅ DO
```python
nova.act(f"book a hotel for two adults in Houston between {startdate} and {enddate} that costs less than $100 per night with the highest star rating. two queen beds preferred but single king also ok. stop when you get to the enter customer details or payment page.")
```

**3. Break up large acts into smaller ones**

❌ DON'T
```python
nova.act("book me a hotel that costs less than $100 with the highest star rating then find the closest car rental and get me car there, finally find a lunch spot nearby and book it at 12:30pm")
```

✅ DO
```python
hotel_address = nova.act_get(f"book a hotel for two adults in Houston between {startdate} and {enddate} that costs less than $100 per night with the highest star rating. two queen beds preferred but single king also ok. return the address of the hotel you booked.").response
nova.act(f“book a restaurant near {hotel_address} at 12:30pm for two people”)
nova.act(f“rent a small sized car between {startdate} and {enddate} from a car rental place near {hotel_address}”)
```

And if the agent still struggles, break it down:

```python
nova.act(f"search for hotels for two adults in Houston between {startdate} and {enddate}")
nova.act("sort by avg customer review")
hotel_address = nova.act_get("book the first hotel that is $100 or less. prefer two queen beds if there is an option. return the address of the hotel you booked.").response
nova.act(f“book a restaurant near {hotel_address} at 12:30pm on {startdate} for two people”)
nova.act(f“search for car rental places near {hotel_address} and navigate to the closest one’s website”)
nova.act(f“rent a small sized car between {startdate} and {enddate}, pickup time 12pm, drop-off 12pm.”)
```

## Workflows

A workflow defines your agent's end-to-end task. Workflows are comprised of act() statements and Python code that orchestrate the automation logic.

The `nova-act` SDK provides a number of convenience wrappers for managing workflows deployed with the NovaAct AWS service. Simply call the CreateWorkflowDefinition API (or use the AWS Console) and get a WorkflowDefinition to get started.

### The Context Manager

The core type driving workflow coordination with the NovaAct service is `Workflow`. This class provides a [context manager](https://peps.python.org/pep-0343/) which will handle calling the necessary workflow API operations from the Amazon Nova Act service. It calls `CreateWorkflowRun` when your run starts and `UpdateWorkflowRun` with the appropriate status when it finishes. It is provided to the `NovaAct` client via a constructor argument, so that all called APIs will be associated with the correct workflow + run (`CreateSession`, `CreateAct`, `InvokeActStep`, `UpdateAct` etc.). See the following example for how to use it:

```python
import os
from nova_act import NovaAct, Workflow

def main():
    with Workflow(
        workflow_definition_name="<your-workflow-name>",
        model_id="nova-act-latest"
    ) as workflow:
        with NovaAct(
            starting_page="https://nova.amazon.com/act/gym/next-dot/search",
            workflow=workflow,
        ) as nova:
            nova.act("Find flights from Boston to Wolf on Feb 22nd")

if name == "main":
    main()
```

#### Retry handling
By default, when a Nova Act request times out, the Nova Act SDK will retry it once. This can be overridden by passing in a `boto_config` object to the Workflow constructor. You can also use this object to override the default 60 second `read_timeout`. For example, to retry a request 4 times (for a total of 5 attempts) with a 90 second timeout:

```python
boto_config = Config(retries={"total_max_attempts": 5, "mode": "standard"}, read_timeout=90)
with Workflow(
    boto_config=boto_config,
    workflow_definition_name="<your-workflow-name>",
    model_id="nova-act-latest"
) as workflow:
```
Note that retrying the same Nova Act request may result in increased cost if the request ends up executing multiple times. For more information on retries including retry modes, please refer to the [botocore retry documentation](https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html).

### The Decorator

For convenience, the SDK also exposes a [decorator](https://peps.python.org/pep-0318/) which can be used to annotate functions to be run under a given workflow. The decorator leverages [ContextVars](https://peps.python.org/pep-0567/) to inject the correct `Workflow` object into each `NovaAct` instance within the function; no need to provide the `workflow` keyword argument! The following syntax provides identical functionality to the previous example:

```python
from nova_act import NovaAct, workflow

@workflow(
    workflow_definition_name="<your-workflow-name>",
    model_id="nova-act-latest",
)
def main():
    with NovaAct(starting_page="https://nova.amazon.com/act/gym/next-dot/search") as nova:
        nova.act("Find flights from Boston to Wolf on Feb 22nd")

if __name__ == "__main__":
    main()
```

#### Configuring AWS Credentials with `boto_session_kwargs`

The `Workflow` class accepts an optional `boto_session_kwargs` parameter for customizing the boto3 Session configuration. **By default, if not provided, the workflow uses `{"region_name": "us-east-1"}`** when AWS credentials are available.

If you need to customize your AWS session (e.g., to use a specific profile or provide explicit credentials), you can pass a custom dictionary to `boto_session_kwargs`. This works with both the **Context Manager** and **Decorator** versions:

**Using the Context Manager:**

```python
from nova_act import NovaAct, Workflow

def main():
    with Workflow(
        workflow_definition_name="<your-workflow-name>",
        model_id="nova-act-latest",
        boto_session_kwargs={
            "profile_name": "my-aws-profile",
            "region_name": "us-east-1"
        }
    ) as workflow:
        with NovaAct(
            starting_page="https://nova.amazon.com/act/gym/next-dot/search",
            workflow=workflow,
        ) as nova:
            nova.act("Find flights from Boston to Wolf on Feb 22nd")

if __name__ == "__main__":
    main()
```

**Using the Decorator:**

```python
from nova_act import NovaAct, workflow

@workflow(
    workflow_definition_name="<your-workflow-name>",
    model_id="nova-act-latest",
    boto_session_kwargs={
        "profile_name": "my-aws-profile",
        "region_name": "us-east-1"
    }
)
def main():
    with NovaAct(starting_page="https://nova.amazon.com/act/gym/next-dot/search") as nova:
        nova.act("Find flights from Boston to Wolf on Feb 22nd")

if __name__ == "__main__":
    main()
```

**Note:** If you don't provide `boto_session_kwargs` and don't use an API key, the workflow will automatically load AWS credentials using boto3 (more details [here](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html) on how boto3 loads AWS credentials).

### Best Practices

#### Multi-threading

The `Workflow` class will work as-is for multi-threaded workflows. See the following example:

```python
from nova_act import NovaAct, Workflow

def multi_threaded_helper(workflow: Workflow):
    with NovaAct(..., workflow=workflow) as nova:
       # nova will have the appropriate workflow run
 
with Workflow(
    workflow_definition_name="my-workflow",
    model_id="nova-act-latest"
) as workflow:
    t = Thread(target=multi_threaded_helper, args=(workflow,))
    t.start()
    t.join()
```

Because the `@workflow` decorator leverages ContextVars for injecting context, and because ContextVars are intentionally designed to be thread-specific, users will have to provide the context to any functions that will run in different threads from where the wrapping function is defined. See the following example:

```python
from contextvars import copy_context
from nova_act import NovaAct, workflow

def multi_threaded_helper():
    with NovaAct(...) as nova:
       # nova will have the appropriate workflow run
 
@workflow(
    workflow_definition_name="my-workflow"
    model_id="nova-act-latest",
)
def multi_threaded_workflow():
    ctx = copy_context()
    t = Thread(target=ctx.run, args=(multi_threaded_helper,))
    t.start()
    t.join()

multi_threaded_workflow()
```

Or, alternatively, use the `workflow` argument directly to manually inject it, as when directly leveraging the `Workflow` class:

```python
from nova_act import NovaAct, get_current_workflow, workflow

def multi_threaded_helper(workflow: Workflow):
    with NovaAct(..., workflow=workflow) as nova:
       # nova will have the appropriate workflow run
 
@workflow(
    workflow_definition_name="my-workflow"
    model_id="nova-act-latest",
)
def multi_threaded_workflow():
    t = Thread(target=multi_threaded_helper, args=(get_current_workflow(),))
    t.start()
    t.join()

multi_threaded_workflow()  
```
#### Multi-processing
The `Workflow` construct does not currently support passing between multi-processing because it maintains a boto3 Session and Client as instance variables, and those objects are not [pickle](https://docs.python.org/3/library/pickle.html)-able. Support coming soon!

### Nova Act CLI

The Nova Act CLI provides a streamlined command-line interface for deploying Python workflows to AWS AgentCore Runtime, handling containerization, ECR management, IAM roles, and multi-region deployments automatically. See the [Nova Act CLI README](./src/nova_act/cli/README.md) for installation and usage instructions.

## Common Building Blocks

### Extracting information from a web page

Use `pydantic` and ask `act_get` to respond to a question about the browser page in a certain schema.

- Make sure you use a schema whenever you are expecting any kind of structured response, even just a bool (yes/no). If a schema is not provided, the returned object will not contain a response.
- Put a prompt to extract information in its own separate `act()` call.

For convenience, the `act_get()` function works the same as `act()` but provides a default `STRING_SCHEMA`, so that a response will always be available in the return object whether or not a specific schema is provided. We recommend using `act_get()` for all extraction tasks, to ensure type safety.

Example:

```python
from nova_act import NovaAct
from pydantic import BaseModel

class Measurement(BaseModel):
    value: float
    unit: str

class PlanetData(BaseModel):
    gravity: Measurement
    average_temperature: Measurement

with NovaAct(
        starting_page="https://nova.amazon.com/act/gym/next-dot"
    ) as nova:
        planet = 'Proxima Centauri b'
        result = nova.act_get(
            f"Go to the {planet} page and return the gravity and average temperature.",
            schema=PlanetData.model_json_schema(),
        )

        # Parse the response into the data model
        planet_data = PlanetData.model_validate(result.parsed_response)

        # Do something with the parsed data
        print(f"✓ {planet} data:\n{planet_data.model_dump_json(indent=2)}")
```

If all you need is a bool response, there's a convenient `BOOL_SCHEMA` constant:
Example:

```python
from nova_act import NovaAct, ActInvalidModelGenerationError, BOOL_SCHEMA
with NovaAct(starting_page="https://nova.amazon.com/act") as nova:
    try:
        result = nova.act_get("Am I logged in?", schema=BOOL_SCHEMA)
    except ActInvalidModelGenerationError as e:
        # act response did not match the schema ¯\_(ツ)_/¯
        print(f"Invalid result: {e}")
    else:
        # result.parsed_response is now a bool
        if result.parsed_response:
            print("You are logged in")
        else:
            print("You are not logged in")
```

### Human-in-the-loop (HITL)

Nova Act's Human-in-the-Loop (HITL) capability enables seamless human supervision within autonomous web workflows. HITL is available in the Nova Act SDK for you to implement in your workflows (not provided as a managed AWS service). When your workflow encounters scenarios requiring human judgment or intervention, HITL can provide tools and user interfaces for supervisors to assist, verify, or take control of the process. 

#### HITL patterns

##### Human approval

Human approval enables asynchronous human decision-making in automated processes. When Nova Act encounters a decision point requiring human judgment, it captures a screenshot of the current state and presents it to a human reviewer via a browser-based interface. Use this when you need binary or multi-choice decisions (Approve/Reject, Yes/No, or selecting from predefined options).

##### UI takeover

UI takeover enables real-time human control of a remote browser session. When Nova Act encounters a task that requires human interaction, it hands control of the browser to a human operator via a live-streaming interface. The operator can interact with the browser using mouse and keyboard in real-time

#### Implementing HITL

Please refer to the [Amazon Nova Act User Guide documentation on HITL](https://docs.aws.amazon.com/nova-act/latest/userguide/hitl.html#implementing-hitl) for implementing HITL in your production workflows.

##### Implementing HITL using the SDK

To implement HITL patterns in the Nova Act SDK, define a class that extends `HumanInputCallbacksBase` and implements two of its abstract methods `approve` and `ui_takeover`. Pass an instance of it to the `human_input_callbacks` argument of the `NovaAct` constructor.

- `approve` - is a callback that will be triggered for the Human approval pattern (e.g Approve expense reports or purchase approvals)
- `ui_takeover` - is a callback that will be triggered for the UI takeover pattern (e.g Solve CAPTCHA challenges)

```
from nova_act import NovaAct, Workflow
from nova_act.tools.human.interface.human_input_callback import (
    ApprovalResponse, HumanInputCallbacksBase, UiTakeoverResponse,
)

class MyHumanInputCallbacks(HumanInputCallbacksBase):
    def approve(self, message: str) -> ApprovalResponse:
        ... 

    def ui_takeover(self, message: str) -> UiTakeoverResponse:
        ...

with NovaAct(
    starting_page=...,
    tty=False,
    human_input_callbacks=MyHumanInputCallbacks(),
) as nova:
    ...
    print(f"Task completed: {result.response}")
```

Refer to [this sample](./src/nova_act/samples/print_number_of_emails.py) for a working example.


### Tool Use Beyond the Browser (Preview)

(Preview) Nova Act allows you to integrate external tools beyond the browser, such as an API Call or Database Query, into workflows. Nova Act SDK allows using a Python function as a tool that can be invoked during a workflow step. To make a Python function available as a tool, annotate it with the @tool decorator. You can pass a list of tools to the NovaAct constructor argument tools.

```
from nova_act import NovaAct, tool

@tool
def my_tool(str: input) -> str:
   ...

with NovaAct(
    starting_page=...,
    tools=[my_tool],
)
```

Refer to [this sample](./src/nova_act/samples/booking_with_data_from_tool.py) for a working example.

Users may also provide tools from an MCP server by leveraging a [Strands MCP Client](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools/mcp-tools/):

```python
from mcp import StdioServerParameters, stdio_client
from nova_act import NovaAct
from strands.tools.mcp import MCPClient

with MCPClient(
    lambda: stdio_client(
        StdioServerParameters(command="uvx", args=["awslabs.aws-documentation-mcp-server@latest"])
    )
) as aws_docs_client:
    with NovaAct(
        starting_page="https://aws.amazon.com/", tools=aws_docs_client.list_tools_sync(),
    ) as nova:
        print(
            nova.act_get(
                "Use the 'search_documentation' tool to tell me about Amazon Bedrock and how to use it with Python."
                "Ignore the web browser; do not click, scroll, type, etc."
            )
        )

```

### Handling ActErrors

Once the `NovaAct` client is started, it might encounter errors during the `act()` execution. All of these error types are included in the [`nova_act.types.act_errors` module](./src/nova_act/types/act_errors.py), and are organized as follows:
1. `ActAgentError`: Indicates requested prompt failed to complete; users may retry with a different request.
   * Examples include: `ActAgentFailed` (the agent raised an error because the task was not possible), `ActInvalidModelGenerationError` (model generated output that could not be interpreted), or `ActExceededMaxStepsError` (`act()` failed to complete within the configured maximum number of steps)
1. `ActExecutionError`: Indicates a local error encountered while executing valid output from the agent
   * Examples include: `ActActuationError` (client encountered an exception while actuating the Browser), or `ActCanceledError` (the user canceled execution).
1. `ActClientError`: Indicates a request to the NovaAct Service was invalid; users may retry with a different request.
   * Examples include: `ActGuardrailsError` (the request was blocked by our RAI guardrails) or `ActRateLimitExceededError` (request was throttled; rate should be reduced).
1. `ActServerError`: Indicates the NovaAct Service encountered an error processing the request.
   * Examples include: `ActInternalServerError` (internal error processing request), `ActBadResponseError` (the service returned a response with unrecognized shape), or `ActServiceUnavailableError` (the service could not be reached.)

Users may catch `ActAgentError`s and `ActClientError`s and retry with the appropriate request; for `ActExecutionError`s and `ActServerError`s, please submit an issue to the team to look into, including (1) your SDK version, (2) your platform + operating system, (3) the full error trace, and (4) steps to reproduce.

### Running multiple sessions in parallel
One `NovaAct` instance can only actuate one browser at a time. However, it is possible to actuate multiple browsers concurrently with multiple `NovaAct` instances! They are quite lightweight. You can use this to parallelize parts of your task, creating a kind of browser use map-reduce for the internet. [This sample](./src/nova_act/samples/search_apartments_calculate_commute.py) shows running multiple sessions in parallel.

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
>>> nova = NovaAct(use_default_chrome_browser=True, clone_user_data_dir=False, user_data_dir=working_user_data_dir, starting_page="https://nova.amazon.com/act/gym/next-dot/search")
>>> nova.start()
>>> nova.act_get("Find flights from Boston to Wolf on Feb 22nd")
...
>>> nova.stop()
>>> quit()
```

### Entering sensitive information

To enter a password or sensitive information (e.g., credit card and social security number), do not prompt the model with the sensitive information. Ask the model to focus on the element you want to fill in. Then use Playwright APIs directly to type the data, using `client.page.keyboard.type(sensitive_string)`. You can get that data in the way you wish: prompting in the command line using [`getpass`](https://docs.python.org/3/library/getpass.html), using an argument, or setting env variable.

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

### Security Options

NovaAct is initialized with secure default behaviors which you may want to relax depending on your use-case.

#### Allow Navigation to Local `file://` URLS

To enable local file navigation, define one or more filepath patterns in `SecurityOptions.allowed_file_open_paths`
```python
from nova_act import NovaAct, SecurityOptions

NovaAct(starting_page="file://home/nova-act/site/index.html", SecurityOptions(allowed_file_open_paths=['/home/nova-act/site/*']))
```

#### Allow File Uploads
To allow the agent to upload files to websites, define one or more filepath patterns in `SecurityOptions.allowed_file_upload_paths`.

```python
from nova_act import NovaAct, SecurityOptions

NovaAct(starting_page="https://example.com", SecurityOptions(allowed_file_upload_paths=['/home/nova-act/shared/*']))
```

#### Filepath Structures
The filepath parameters support the following formats:
- `["/home/nova-act/shared/*"]` - Allow from specific directory
- `["/home/nova-act/shared/file.txt"]` - Allow a specific filepath
- `["*"]` - Enable for all paths
- `[]` - Disable the feature (Default)

### State Guardrails

State guardrails allow you to control which URLs the agent can visit during execution. You can provide a callback function that inspects the browser state after each observation and decides whether to allow or block continued execution. If blocked, `act()` will raise `ActStateGuardrailError`. This is useful for preventing the agent from navigating to unauthorized domains or sensitive pages.

```python
from nova_act import NovaAct, GuardrailDecision, GuardrailInputState
from urllib.parse import urlparse
import fnmatch

def url_guardrail(state: GuardrailInputState) -> GuardrailDecision:
    hostname = urlparse(state.browser_url).hostname
    if not hostname:
        return GuardrailDecision.BLOCK

    # Example URL block-list
    blocked = ["*.blocked-domain.com", "*.another-blocked-domain.com"]
    if any(fnmatch.fnmatch(hostname, pattern) for pattern in blocked):
        return GuardrailDecision.BLOCK

    # Example URL allow-list
    allowed = ["allowed-domain.com", "*.another-allowed-domain.com"]
    if any(fnmatch.fnmatch(hostname, pattern) for pattern in allowed):
        return GuardrailDecision.PASS

    return GuardrailDecision.BLOCK

with NovaAct(starting_page="https://allowed-domain.com", state_guardrail=url_guardrail) as nova:
    # The following will be blocked if agent tries to visit a blocklisted domain or leave one of the allowlisted domains
    nova.act("Navigate to the homepage")
```

### Captchas

You should use the `ui_takeover` callback (see [HITL](#human-in-the-loop-hitl)) if your script encounters captchas in certain places. This will allow redirecting the step of solving Captcha to a human.

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

NovaAct can natively upload files using the appropriate upload action on the page. To do that, first you must allow NovaAct to access the file for upload. Then instruct it to
upload it by filename:

```python
upload_filename = "/upload_path/upload_me.pdf"

with NovaAct(..., security_options=SecurityOptions(allowed_file_upload_paths=["/upload_path/*"])) as nova:
    nova.act(f"upload {upload_filename} using the upload receipt button")
```

> **Important security note**:
>
> Pick `allowed_file_upload_paths` narrowly to minimize NovaAct's access to your filesystem to avoid data exfiltration by malicious sites or web content.

### Working with Browser Dialogs

Playwright automatically dismisses browser native dialogs such as [alert](https://developer.mozilla.org/en-US/docs/Web/API/Window/alert), [confirm](https://developer.mozilla.org/en-US/docs/Web/API/Window/confirm), and [prompt](https://developer.mozilla.org/en-US/docs/Web/API/Window/prompt) by default. To handle them manually, register a dialog handler before Nova Act performs the action that triggers the dialog. For example:

```python
def handle_dialog(dialog):
    """Handle dialog by printing its message and accepting it."""
    print(f"Dialog message: {dialog.message}")
    dialog.accept()  # Accept and dismiss the dialog
    # dialog.dismiss()  # Or dismiss/cancel the dialog

# Register the handler
nova.page.on("dialog", handle_dialog)
# Trigger the dialog
nova.act("Do something that results in a dialog")
# Unregister the handler
nova.page.remove_listener("dialog", handle_dialog)
```

For more details, see the [Playwright documentation](https://playwright.dev/python/docs/dialogs#alert-confirm-prompt-dialogs).

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

### Time worked tracking utility

The time_worked utility tracks and reports the approximate time spent by the agent working on tasks, excluding time spent waiting for human input. This helps you understand the actual agent execution time.

#### How It Works
Approximate time worked is calculated using this basic formula:
```
time_worked = (end_time - start_time) - human_wait_time
```

When an `act()` call completes (successfully or with an error), the following is calculated:
- **Approx. Time Worked**: Total execution time (end time minus start time) minus any time spent waiting for human input
- **Human Wait Time**: Time spent waiting for `approve()` or `ui_takeover()` callbacks from when the callback is issued to when the agent execution continues

#### Console Output

At the end of each `act()` call, you'll see a time worked summary in the console, as well as in the JSON and HTML reports:

Without human input:
```
⏱️ Approx. Time Worked: 11.8s
```

With human input:
```
⏱️  Approx. Time Worked: 28.3s (excluding 4.5s human wait)
```

#### Important Disclaimer

> **Note:** Time worked calculations are approximate and may have inaccuracies due to system timing variations, network latency, or other factors. This metric should be viewed as a utility to help understand agent execution patterns and should not be used for formal time tracking or billing purposes.

### Recording a session
 
You can easily record an entire browser session locally by setting the `logs_directory` and specifying `record_video=True` in the constructor for `NovaAct`.

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
    starting_page="https://nova.amazon.com/act/gym/next-dot/search",
    boto_session=boto_session,  # You may use API key here instead
    stop_hooks=[s3_writer]
) as nova:
    result = nova.act_get("Find flights from Boston to Wolf on Feb 22nd")
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

> **Note**: When the Nova Act SDK and Bedrock AgentCore Browser run on different operating systems (e.g., SDK on MacOS and AgentCore Browser on Linux), keyboard commands may not translate correctly between systems. This impacts certain SDK functions like `agent_type()`, which uses keyboard shortcuts (such as `ControlOrMeta+A` for "select all") that are OS-dependent. This behavior is an expected consequence of the cross-OS integration architecture and should be considered when developing automations that use keyboard input methods.

## Known limitations
Our vision for Nova Act is to provide key capabilities to build useful agents at scale. If you encounter limitations with Nova Act — please provide feedback to [nova-act@amazon.com](mailto:nova-act@amazon.com?subject=Nova%20Act%20Bug%20Report) to help us make it better.


For example:

* `act()` cannot interact with non-browser applications;
* `act()` cannot interact with the browser window. This means that browser modals such as those requesting access to use your location don't interfere with act() but must be manually acknowledged if desired;
* Screen size constraints;
  * Nova Act is optimized for resolutions between `864×1296` and `1536×2304`; and
  * Performance may degrade outside this range

Learn more in the AWS AI Service Card for Amazon Nova Act.

## Reference


### Initializing `NovaAct`

The constructor accepts the following:

* `starting_page (str)`: The URL of the starting page; supports both web URLs (`https://`) and local file URLs (`file://`) (required argument)
  * Note: file URLs require passing `ignore_https_errors=True` to the constructor
* `headless (bool)`: Whether to launch the browser in headless mode (defaults to `False`)
* `user_data_dir (str)`: Path to a [user data directory](https://chromium.googlesource.com/chromium/src/+/master/docs/user_data_dir.md#introduction), which stores browser session data like cookies and local storage (defaults to `None`).
* `nova_act_api_key (str)`: The API key you generated for authentication; required if the `NOVA_ACT_API_KEY` environment variable is not set. If passed, takes precedence over the environment variable.
* `logs_directory (str)`: The directory where NovaAct will output its logs, run info, and videos (if `record_video` is set to `True`).
* `record_video (bool))`: Whether to record video and save it to `logs_directory`. Must have `logs_directory` specified for video to record.
* `proxy (dict)`: Proxy configuration for the browser. Should be a dictionary containing:
  * `server` (required): The proxy server URL (must start with `http://` or `https://`)
  * `username` (optional): Username for proxy authentication
  * `password` (optional): Password for proxy authentication
  * Note: Proxy is not supported when connecting to a CDP endpoint or using the default Chrome browser
* `human_input_callbacks` (optional): An implementation of human input callbacks. If not provided, a request for human input tool will not be made.
* `tools` (optional): A list of client provided tools.

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
    metadata: ActMetadata

class ActMetadata:
    session_id: str | None
    act_id: str | None
    num_steps_executed: int
    start_time: float
    end_time: float
    prompt: string
```

If a schema is passed to `act()` (the `act_get()` function conveniently provides a default `STRING_SCHEMA`), then the returned object will be an `ActGetResult`, a subclass which includes the raw and structured response:

```python
class ActGetResult(ActResult):
    response: str | None
    parsed_response: JSONType
    valid_json: bool | None
    matches_schema: bool | None
```

#### Do it programmatically

`NovaAct` exposes a Playwright [`Page`](https://playwright.dev/python/docs/api/class-page) object directly under the `page` attribute.

This can be used to retrieve current state of the browser, for example a screenshot or the DOM, or actuate it:

```python
screenshot_bytes = nova.page.screenshot()
dom_string = nova.page.content()
nova.page.keyboard.type("hello")
```

## Disclosures

Note: When using the Nova Act Playground and/or choosing Nova Act developer tools with API key authentication, access and use are subject to the nova.amazon.com Terms of Use. When choosing Nova Act developer tools with AWS IAM authentication and/or deploying workflows to the Nova Act AWS service, your AWS Service Terms and/or Customer Agreement (or other agreement governing your use of the AWS Service) apply.

1. Nova Act may not always get it right. 
2. ⚠️ Please be aware that Nova Act may encounter commands in the content it observes on third party websites, including user-generated content on trusted websites such as social media posts, search results, forum comments, news articles, and document attachments. These unauthorized commands, known as prompt injections, may cause the model to make mistakes or act in a manner that differs from its instructions, such as ignoring your instructions, performing unauthorized actions, or exfiltrating sensitive data. To reduce the risks associated with prompt injections, it is important to monitor Nova Act and review its actions, especially when processing untrusted user-contributed content.
3. We recommend you do not provide sensitive information to Nova Act, such as account passwords. Note that if you use sensitive information through Playwright calls, the information could be collected in screenshots if it appears unobstructed on the browser when Nova Act is engaged in completing an action. (See Entering sensitive information below.).
4. When choosing developer tools on nova.amazon.com/act with API key authentication, we collect information on interactions with Nova Act, including in-browser screenshots to develop and improve our services. Email us at nova-act@amazon.com to request deletion of your Nova Act data.
5. Do not share your API key generated on https://nova.amazon.com/act. Anyone with access to your API key can use it to operate Nova Act under your Amazon account. If you lose your API key or believe someone else may have access to it, go to https://nova.amazon.com/act to deactivate your key and obtain a new one.
6. If you are using our browsing environment defaults, look for `NovaAct` in the user agent string to identify our agent. If you operate Nova Act in your own browsing environment or customize the user agent, we recommend that you include that same string.

## Report a Bug

Help us improve! If you notice any issues, please let us know by submitting a bug report via nova-act@amazon.com. 


Be sure to include the following in the email:
- Description of the issue;
- Session ID, which will have been printed out as a console log message; and
- Script of the workflow you are using.

Your feedback is valuable in ensuring a better experience for everyone.

Thanks for experimenting with Nova Act!

