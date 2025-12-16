# Frequently Asked Questions

## General Questions

### General Question 1: What can Nova Act do?
Nova Act can:

* Interact with web interfaces
* Extract information from web pages
* Perform automated UI tasks
* Human-in-the-loop (HITL)
* Tool use beyond the browser (Preview)

For more information, see [What is Amazon Nova Act?](https://docs.aws.amazon.com/nova-act/latest/userguide/what-is-nova-act.html)

### General Question 2: How do I get access to Nova Act?
There are two main ways to access Nova Act:
1. For experimentation and previewing new Nova Act model versions for free, through [nova.amazon.com/act](https://nova.amazon.com/act) using API keys
2. For production through [Nova Act AWS Service](https://aws.amazon.com/nova/act/), using IAM AWS credentials

For more information, see [Getting started with Nova Act](https://docs.aws.amazon.com/nova-act/latest/userguide/getting-started.html)

### General Question 3: Do we have details about pricing?
Yes, see the Nova Act section on [Amazon Nova Pricing](https://aws.amazon.com/nova/pricing/)

### General Question 4: In which regions is Nova Act available?

1. For the Nova Act free version at [nova.amazon.com/act](https://nova.amazon.com/act), Nova Act is available wherever the nova.amazon.com site is released.

2. For the Nova Act AWS Service, see the regions listed in [Nova Act Availability](https://docs.aws.amazon.com/nova-act/latest/userguide/what-is-nova-act.html#availability)

### General Question 5: When will Nova Act be available in additional regions?
We have not published timelines for additional region availability.

### General Question 6: I created a workflow with Nova Act. How can I share this with the community?
We highly encourage users to share their workflows with others in the community. Please make a Pull Request (PR) with your script in the Nova Act GitHub [samples folder](https://github.com/aws/nova-act/tree/main/src/nova_act/samples). Our team will analyze your workflow and, if approved, it will be merged into the repository.

You can also share any workflows that you create using the [nova.amazon.com playground](https://internal.nova.amazon.com/act?tab=playground).   After you create and run your agent, you can post it on the Nova Public Gallery by clicking the 'Share' button. 

### General Question 7: Where can I find more information?
Resources available include:

* Nova Act free version: [https://nova.amazon.com/act](https://nova.amazon.com/act)
* Nova Act AWS product page: [https://aws.amazon.com/nova/act/](https://aws.amazon.com/nova/act/)
* Nova Act Blog Posts: [https://labs.amazon.science/blog/nova-act](https://labs.amazon.science/blog)
* SDK GitHub repository: [https://github.com/aws/nova-act](https://github.com/aws/nova-act)
* Code samples: [https://github.com/amazon-agi-labs/nova-act-samples](https://github.com/amazon-agi-labs/nova-act-samples)
* AWS User Guide: [https://docs.aws.amazon.com/nova-act/](https://docs.aws.amazon.com/nova-act/)

## Technical Questions

### Technical Question 1: Can Nova Act handle authentication and passwords?
For security reasons, Nova Act has guardrails that prevent it from handling password inputs or sensitive authentication data. We recommend to use PlayWright APIs for these cases. See [Entering sensitive information](https://github.com/aws/nova-act/blob/main/README.md#entering-sensitive-information) for details.

### Technical Question 2: Can this model be used for general computer use style use cases as well?
Currently, Nova Act is limited to browser automation only. We do not support direct computer use yet. However, we have been able to do simple things by launching a browser window pointed to a remote desktop OS VM and then actuating the window.

### Technical Question 3: Is Nova Act compatible with Strands or other agent orchestration frameworks?
Yes, Nova Act can be integrated into Strands as a tool.  See [Strands Agent Integrations](https://docs.aws.amazon.com/nova-act/latest/userguide/strands.html) for details.

### Technical Question 4: What are some of the common use cases for Nova Act?
We are seeing customers use Nova Act across a variety of use cases, including:
* Quality Assurance and testing (QA)
* Form filling
* Search and data extraction
* Shopping

### Technical Question 5: Does Nova Act support headless browsing or search?
Yes, you can set the parameter `headless` to `True` to run Nova Act in headless mode. The default is `False`.

### Technical Question 6: Can it copy text from a browser window and then paste it into an installed application, for example Excel?
Currently, Nova Act is limited to browser automation only. However, you can use Python functions to return text, JSON or even create a CSV file.

### Technical Question 7: Does the SDK work only with the Nova Act model? Or can the model be swapped?
The SDK only works with the Nova Act model.

### Technical Question 8: Is the SDK only available for Python?
Yes, the SDK is currently only available for Python.

### Technical Question 9: When running a workflow, will Nova Act ask the user for clarification if needed to confirm certain tasks?
Yes, Nova Act can be configured to use Human-in-the-loop (HITL).  See the [AWS User Guide](https://docs.aws.amazon.com/nova-act/latest/userguide/hitl.html) for details.

### Technical Question 10: Did the Nova Act team publish any performance metrics using the standard public benchmarks?
Yes, you can refer to the benchmark metrics we published in our [blog post](https://labs.amazon.science/blog/amazon-nova-act-service). We've focused on scoring >90% on internal evals of capabilities that trip up other models, such as date picking, drop downs, and pop-ups, and achieving best-in-class performance on benchmarks like ScreenSpot and GroundUI Web which most directly measure the ability for our model to actuate the web.

### Technical Question 11: Can I use the Nova Act SDK within iPython or Jupyter notebooks?
No, Nova Act SDK is not currently supported within those environments.

### Technical Question 12: Can I run this on Windows?
Yes, Nova Act works on both WSL2 and Windows 10+.

### Technical Question 13: Is there a way to speed up the execution?
Breaking down your prompt into more discrete steps can help.

### Technical Question 14: Is there a way to have Nova Act remember what it did so it could re-use what it learned about the UI?
You can use the Chrome user data directory to save the session state and restart mid-point.

