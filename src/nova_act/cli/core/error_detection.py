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
"""Detection and message helpers for error handling."""

import re
import subprocess
from pathlib import Path

from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError


def is_credential_error(error: Exception) -> bool:
    """Check if error is AWS credential related."""
    if isinstance(error, (NoCredentialsError, PartialCredentialsError)):
        return True

    if isinstance(error, ClientError):
        error_code = error.response.get("Error", {}).get("Code", "")
        return error_code in ["InvalidClientTokenId", "UnrecognizedClientException"]

    return False


def is_permission_error(error: Exception) -> bool:
    """Check if error is AWS permission denied."""
    if isinstance(error, ClientError):
        error_code = error.response.get("Error", {}).get("Code", "")
        return error_code in ["AccessDenied", "AccessDeniedException", "UnauthorizedOperation"]
    return False


def extract_permission_from_error(error: ClientError) -> str | None:
    """Extract required permission from AWS error message."""
    error_message = error.response.get("Error", {}).get("Message", "")
    match = re.search(r"not authorized to perform: ([\w:]+)", error_message)
    if match:
        return match.group(1)
    return None


def extract_operation_name(error: ClientError) -> str:
    """Extract operation name from ClientError."""
    return error.operation_name if hasattr(error, "operation_name") else "unknown"


def is_docker_running() -> bool:
    """Check if Docker daemon is running."""
    try:
        subprocess.run(["docker", "ps"], capture_output=True, check=True, timeout=5)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_credential_error_message() -> str:
    """Generate AWS credentials not found message with setup steps."""
    return (
        "❌ AWS Credentials Not Found\n\n"
        "The Nova Act CLI requires AWS credentials to deploy and manage workflows.\n\n"
        "How to configure credentials:\n"
        "  1. AWS CLI: aws configure\n"
        "  2. Environment variables:\n"
        "     export AWS_ACCESS_KEY_ID=your_key\n"
        "     export AWS_SECRET_ACCESS_KEY=your_secret\n"
        "  3. AWS SSO: aws sso login --profile your-profile\n\n"
        "Verify credentials:\n"
        "  aws sts get-caller-identity\n\n"
        "Documentation: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html"
    )


def get_permission_error_message(
    operation: str, workflow_name: str, region: str, account_id: str, permission: str | None = None
) -> str:
    """Generate AWS permission denied message with required permissions."""
    permission_text = f"  - {permission}\n\n" if permission else ""

    return (
        f"❌ AWS Permission Denied: {operation}\n\n"
        f"Operation: deploying workflow '{workflow_name}'\n"
        f"Region: {region}\n"
        f"Account: {account_id}\n\n"
        "The CLI needs permissions to perform this operation.\n\n"
        f"Required permission:\n{permission_text}"
        "To fix:\n"
        "  1. Ask your AWS administrator to grant required permissions\n"
        "  2. Or switch to a profile with permissions: export AWS_PROFILE=admin-profile"
    )


def get_docker_not_running_message() -> str:
    """Generate Docker daemon not running message with startup steps."""
    return (
        "❌ Docker Build Failed: Docker Not Running\n\n"
        "The CLI uses Docker to build workflow container images.\n\n"
        "Problem: Cannot connect to Docker daemon\n\n"
        "To fix:\n"
        "  1. Start Docker Desktop (macOS/Windows)\n"
        "     → Open Docker Desktop application\n"
        "  \n"
        "  2. Start Docker daemon (Linux)\n"
        "     → sudo systemctl start docker\n"
        "  \n"
        "  3. Verify Docker is running:\n"
        "     → docker ps\n\n"
        "Install Docker: https://docs.docker.com/get-docker/"
    )


def get_docker_build_failed_message(build_path: str) -> str:
    """Generate Docker build failed message with debugging steps."""
    return (
        f"❌ Docker Build Failed\n\n"
        f"Build directory: {build_path}\n\n"
        "Problem: Docker build command failed\n\n"
        "Common causes:\n"
        "  1. Dockerfile syntax error\n"
        "     → Check build directory for Dockerfile\n"
        "  \n"
        "  2. Missing dependencies in requirements.txt\n"
        "     → Verify all packages are available on PyPI\n"
        "  \n"
        "  3. Network issues downloading base image\n"
        "     → Check internet connection\n\n"
        f"Build artifacts preserved in: {build_path}\n"
        f"To debug: cd {build_path} && docker build -t test ."
    )


def get_entry_point_missing_main_message(entry_point_path: Path) -> str:
    """Generate missing main() function message with example."""
    return (
        f"❌ Invalid Entry Point: Missing main() Function\n\n"
        f"File: {entry_point_path}\n\n"
        "AgentCore workflows require an entry point function that receives the workflow payload.\n\n"
        "Expected structure:\n"
        "  def main(payload):\n"
        '      """\n'
        "      Args:\n"
        "          payload: Dictionary containing workflow input data\n"
        "      \n"
        "      Returns:\n"
        "          Dictionary with workflow results\n"
        '      """\n'
        '      print(f"Received payload: {payload}")\n'
        '      return {"status": "success"}\n\n'
        "Your file does not contain a main() function.\n\n"
        "To fix:\n"
        "  1. Add a main(payload) function to your script\n"
        "  2. Specify a different entry point: --entry-point other_file.py\n"
        "  3. Skip validation (advanced): --skip-entrypoint-validation"
    )


def get_entry_point_missing_parameter_message(entry_point_path: Path) -> str:
    """Generate main() missing parameter message with fix steps."""
    return (
        f"❌ Invalid Entry Point: main() Missing Parameter\n\n"
        f"File: {entry_point_path}\n\n"
        "The main() function must accept at least one parameter for the workflow payload.\n\n"
        "Expected:\n"
        "  def main(payload):\n"
        "      # Your workflow logic\n"
        '      return {"result": "success"}\n\n'
        "Current:\n"
        "  def main():  # ❌ Missing parameter\n\n"
        "To fix:\n"
        "  1. Add a parameter to main(): def main(payload):\n"
        "  2. Or skip validation: --skip-entrypoint-validation"
    )


def get_workflow_not_found_message(name: str, region: str, account_id: str, available_workflows: list[str]) -> str:
    """Generate workflow not found message with available options."""
    if not available_workflows:
        return (
            f"❌ Workflow Not Found: '{name}'\n\n"
            f"Region: {region}\n"
            f"Account: {account_id}\n\n"
            "No workflows are configured in this region.\n\n"
            "To fix:\n"
            "  1. Create the workflow first:\n"
            f"     act workflow create --name {name}\n"
            "  \n"
            "  2. Or list workflows in other regions:\n"
            "     act workflow list --region us-west-2\n"
            "  \n"
            "  3. Or deploy directly without pre-creation:\n"
            "     act workflow deploy --source-dir ./my-code\n\n"
            "Note: Workflows are region-specific. Create workflows in each region where you want to deploy."
        )

    workflows_list = "\n  - ".join(available_workflows)
    return (
        f"❌ Workflow Not Found: '{name}'\n\n"
        f"Region: {region}\n"
        f"Account: {account_id}\n\n"
        f"Available workflows in this region:\n  - {workflows_list}\n\n"
        "To fix:\n"
        "  1. Use an existing workflow name from the list above\n"
        "  2. Or create a new workflow:\n"
        f"     act workflow create --name {name}\n"
        "  3. Or list all workflows:\n"
        "     act workflow list"
    )


def get_state_corrupted_message(state_file: Path, error: str) -> str:
    """Generate state file corrupted message with recovery steps."""
    return (
        f"❌ Configuration State Corrupted\n\n"
        f"The CLI stores workflow configuration locally but the state file is corrupted.\n\n"
        f"Location: {state_file}\n\n"
        "To fix:\n"
        "  1. Backup current state:\n"
        "     mv ~/.nova-act/state ~/.nova-act/state.backup\n"
        "  \n"
        "  2. Reset CLI state:\n"
        "     rm -rf ~/.nova-act/state\n"
        "  \n"
        "  3. Re-create workflow configurations:\n"
        "     act workflow create --name my-workflow\n\n"
        "Important: This only affects local configuration. "
        "Your AWS resources (AgentCore runtimes, ECR images) are not affected.\n\n"
        f"Original error: {error}"
    )


def get_state_write_failed_message(state_file: Path, error: str) -> str:
    """Generate state write failed message with troubleshooting."""
    return (
        f"❌ Configuration State Write Failed\n\n"
        f"The CLI could not save workflow configuration.\n\n"
        f"Location: {state_file}\n\n"
        "To fix:\n"
        "  1. Check file permissions:\n"
        f"     ls -la {state_file.parent}\n"
        "  \n"
        "  2. Check disk space:\n"
        "     df -h\n"
        "  \n"
        "  3. Check directory ownership:\n"
        f"     ls -ld {state_file.parent}\n\n"
        f"Original error: {error}"
    )
