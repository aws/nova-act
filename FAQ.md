# Frequently Asked Questions

## General Questions

### General Question 1: What can Nova Act do?
Nova Act can:

* Interact with web interfaces
* Extract information from web pages
* Perform automated UI tasks

### General Question 2: How do I get access to Nova Act?
Go to [nova.amazon.com/act](https://nova.amazon.com/act) and sign in with your amazon.com account. You can generate your API key and get started building workflows.

### General Question 3: Can I connect Nova Act with my AWS account?
No, Nova Act is not available as an AWS product, but AWS users are more than welcome to try it out. During this experimental phase, you need to sign up using your amazon.com account. Refer to Question 1 to learn how to access Nova Act. 

### General Question 4: Do we have details about pricing?
Nova Act is a research preview which is free to use. Customers get a daily quota of requests.

### General Question 5: In which regions is Nova Act available?
Nova Act is currently available in the following regions:

  - United States
  - Canada
  - Mexico
  
If you are interested in using Nova Act in a different region, please let us know. We are tracking feature requests in our GitHub repo, so please +1 and add a comment where you'd like to see us expand to next.

### General Question 6: When will Nova Act be available in my region?
We have not published timelines for additional region availability.

### General Question 7: I created a workflow with Nova Act. How can I share this with the community?
We highly encourage users to share their workflows with others in the community. Please make a Pull Request (PR) with your script in the Nova Act GitHub [samples folder](https://github.com/aws/nova-act/tree/main/src/nova_act/samples). Our team will analyze your workflow and, if approved, it will be merged into the repository.

### General Question 8: Where can I find more information?
Resources available include:

* Nova Act Web Page: [https://nova.amazon.com/act](https://nova.amazon.com/act)
* Nova Act Blog Post: [https://labs.amazon.science/blog/nova-act](https://labs.amazon.science/blog/nova-act)
* GitHub repository: [https://github.com/aws/nova-act](https://github.com/aws/nova-act)
* Code samples: [https://github.com/aws/nova-act/tree/main/src/nova_act/samples](https://github.com/aws/nova-act/tree/main/src/nova_act/samples)

## Technical Questions

### Technical Question 1: Can Nova Act handle authentication and passwords?
For security reasons, Nova Act has guardrails that prevent it from handling password inputs or sensitive authentication data. We recommend to use PlayWright APIs for these cases. Check the section about how to enter sensitive information in our documentation: Entering sensitive information.

### Technical Question 2: Can this model be used for general computer use style use cases as well?
Currently, Nova Act is limited to browser automation only. We do not support direct computer use yet. However, we have been able to do simple things by launching a browser window pointed to a remote desktop OS VM and then actuating the window. 

### Technical Question 3: Is Nova Act compatible with LangChain or other tools?
Nova Act is an independent agentic system in itself and it works end-to-end from the `act()` call to the model. It is not designed to be integrated with LangChain.

### Technical Question 4: What are some of the common use cases for Nova Act?
We are seeing users experiment with Nova Act in many different areas. Some common themes are in automating tasks within QA testing, market research, customer support, and simulating customer journeys.

### Technical Question 5: Does Nova Act support headless browsing or search?
Yes, you can set the parameter `headless` to `True` to run Nova Act in headless mode. The default is `False`.

### Technical Question 6: Can it copy text from a browser window and then paste it into an installed application, for example Excel?
Currently, Nova Act is limited to browser automation only. However, you can use Python functions to return text, JSON or even create a CSV file.

### Technical Question 7: Does the SDK work only with the Nova Act model? Or can the model be swapped?
The SDK only works with the Nova Act model.

### Technical Question 8: Is the SDK only available for Python?
Yes, the SDK is currently only available for Python.

### Technical Question 9: When running a workflow, will Nova Act ask the user for clarification if needed to confirm certain tasks?
Nova Act does not have a function to ask users for clarification. Nova Act was designed to be fully automated and we do not expect users to keep monitoring what it is doing. When you create your workflow, you can leverage Python functions to create conditions where the Agent will take specific tasks.

### Technical Question 10: Did the Nova Act team publish any performance metrics using the standard public benchmarks?
Yes, you can refer to the benchmark metrics we published in our [blog post](https://labs.amazon.science/blog/nova-act). We've focused on scoring >90% on internal evals of capabilities that trip up other models, such as date picking, drop downs, and pop-ups, and achieving best-in-class performance on benchmarks like ScreenSpot and GroundUI Web which most directly measure the ability for our model to actuate the web.

### Technical Question 11: Can I use the Nova Act SDK within iPython or Jupyter notebooks?
No, Nova Act SDK is not currently supported within those environments.

### Technical Question 12: Can I run this on Windows?
Nova SDK is officially supported on MacOS and Ubuntu. Users have been successful running the Nova Act SDK on an Ubuntu instance running on WSL2. You can learn more about this setup [here](https://documentation.ubuntu.com/wsl/en/latest/howto/install-ubuntu-wsl2/).

### Technical Question 13: Is there a way to speed up the execution?
Breaking down your prompt into more discrete steps can help. Higher level reasoning often takes longer to execute, so taking a step-wise approach may help.

### Technical Question 14: Is there a way to have Nova Act remember what it did so it could re-use what it learned about the UI?
You can use the Chrome user data directory to save the session state and restart mid-point.

