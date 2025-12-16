# Nova Act

Amazon Nova Act is available as an AWS service to build and manage fleets of reliable AI agents for automating production UI workflows at scale. Nova Act completes repetitive UI workflows in the browser and escalates to a human supervisor when appropriate. You can define workflows by combining the flexibility of natural language with Python code. Start by exploring in the web playground at nova.amazon.com/act, develop and debug in your IDE, deploy to AWS, and monitor your workflows in the AWS Console, all in just a few steps.

(Preview) Nova Act also integrates with external tools through API calls, remote MCP, or agentic frameworks, such as Strands Agents.

# Nova Act CLI

Deploy Nova Act workflows to AWS AgentCore Runtime with minimal setup!

## Overview

The Nova Act CLI provides a streamlined process for deploying workflows to AWS AgentCore Runtime. It handles containerization, ECR management, IAM roles, S3 bucket creation and AgentCore Runtime deployments automatically with account-based configuration management.

IMPORTANT: The Nova Act CLI is a convenience utility to quickstart the creation and deployment of remote Nova Act workflows. It **SHOULD NOT** be used as a dependency in production code!

## Installation

```bash
pip install nova-act[cli]
```

## Quick Start

### Option 1: Named Workflow Management (Recommended)
Create and manage named AWS Nova Act workflows for repeated deployments and console visibility:

```bash
# 1. Create workflow configuration
act workflow create --name my-workflow

# 2. Deploy the workflow
act workflow deploy --name my-workflow --source-dir /path/to/project

# 3. Run the deployed workflow
act workflow run --name my-workflow --payload '{"input": "data"}'
```

### Option 2: Quick Deploy
Deploy any Python script directly without pre-creating a named workflow:

```bash
# Deploy a single script file
act workflow deploy --entry-point /path/to/your/script.py

# Deploy a directory with auto-detected entry point
act workflow deploy --source-dir /path/to/your/project

# Deploy with specific entry point
act workflow deploy --source-dir /path/to/project --entry-point my_script.py

# Run the deployed workflow
# The above commands auto-create a workflow name like: workflow-20251130-120945
act workflow run --name <auto-created-workflow-name> --payload '{"input": "test data"}'
```

**Note:** Quick deploy creates a persistent workflow with auto-generated name. The workflow remains in your configuration and can be managed with standard workflow commands (`list`, `show`, `delete`, etc.).

## Creating A WorkflowDefinition

### Using Nova Act CLI

The `act workflow create --name <workflow-name>` command automatically creates a workflow definition with the provided name and the default Nova Act CLI S3 bucket (`nova-act-{account-id}-{region}`).

### Using AWS CLI

**Note:** You may need to update your AWS CLI to the latest version to access the `nova-act` service commands.

```bash
# Create workflow definition with S3 export configuration
aws nova-act create-workflow-definition \
  --name my-workflow \
  --export-config '{
    "s3BucketName": "my-bucket",
    "s3KeyPrefix": "nova-act-workflows"
  }' \
  --region us-east-1
```

### Using AWS SDK (boto3)

**Note:** This code sets up an AWS resource (WorkflowDefinition) that will later be used with the AWS Nova Act service in your actual workflow code that uses the Nova Act SDK. There is no need to recreate a workflow definition at runtime.

```python
import boto3

# Create boto3 client for Nova Act workflow management
client = boto3.client('nova-act')

# Create workflow definition with S3 export configuration
response = client.create_workflow_definition(
    name='my-workflow',  # Replace with your workflow name
    exportConfig={
        's3BucketName': 'my-bucket',  # Replace with your S3 bucket
        's3KeyPrefix': 'nova-act-workflows'
    }
)

print(f"Created workflow: {response['name']}")
```

## Commands

### Core Workflow Commands

- **`create`** - Register a new workflow in configuration
- **`deploy`** - Build and deploy workflow to AWS AgentCore
- **`run`** - Execute deployed workflow with payload
- **`list`** - Show all configured workflows
- **`show`** - Display detailed workflow information
- **`update`** - Modify workflow configuration (source directory, entry point)
- **`delete`** - Remove workflow from configuration

**Note**: Use `deploy` command to rebuild and redeploy with updated code.


### Deployment Modes

**Quick Deploy**: Automatically creates workflow for immediate deployment
```bash
act workflow deploy --source-dir /path/to/code
# Generates name like: workflow-20251130-120945
```

**Note:** Workflows created via quick deploy are persistent, not temporary.

**Named Workflow**: Uses pre-configured workflow settings
```bash
act workflow deploy --name my-workflow --source-dir /path/to/code
```

## Configuration

Workflows are stored in separate state files per AWS account and region in `~/.act_cli/state/{account_id}/{region}/workflows.json` with file locking for concurrent access protection. User preferences are stored in `~/.act_cli/config.yml`.

**State File Structure** (`~/.act_cli/state/123456789012/us-east-1/workflows.json`):
```json
{
  "workflows": {
    "my-workflow": {
      "name": "my-workflow",
      "directory_path": "/path/to/build/dir/",
      "created_at": "2024-10-30T12:51:39.000Z",
      "workflow_definition_arn": "arn:aws:nova-act:us-east-1:123456789012:workflow-definition/my-workflow",
      "deployments": {
        "agentcore": {
          "deployment_arn": "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/my_workflow_abc123",
          "image_uri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/nova-act-cli-default:my-workflow-20241030-125139",
          "image_tag": "my-workflow-20241030-125139"
        }
      },
      "metadata": null,
      "last_image_tag": "my-workflow-20241030-125139"
    }
  },
  "last_updated": "2024-10-30T12:51:39.000Z",
  "version": "1.0"
}
```

**Note:** Region and account_id are encoded in the file path hierarchy, not stored in the workflow object.

### State Management

**File Locking**: Concurrent CLI operations are protected with file locks (30s timeout)

**State Isolation**: Each AWS account + region combination has separate state:
```
~/.act_cli/state/
├── 123456789012/
│   ├── us-east-1/
│   │   └── workflows.json
│   └── us-west-2/
│       └── workflows.json
└── 987654321098/
    └── us-east-1/
        └── workflows.json
```

### State Schema Fields

**WorkflowInfo Fields:**
- `name` - Workflow identifier
- `directory_path` - Path to source/build directory (updated on each deployment)
- `created_at` - Workflow creation timestamp
- `workflow_definition_arn` - ARN of associated WorkflowDefinition (optional)
- `deployments.agentcore` - AgentCore deployment information (if deployed)
  - `deployment_arn` - ARN of AgentCore runtime
  - `image_uri` - Full ECR image URI
  - `image_tag` - Image tag used for deployment
- `metadata` - Custom metadata dictionary (optional)
- `last_image_tag` - Most recent image tag used

**RegionState Fields:**
- `workflows` - Dictionary of workflow name to WorkflowInfo
- `last_updated` - Timestamp of last state update
- `version` - State schema version

**Note:** Region and account ID are not stored in the workflow object; they are encoded in the file path hierarchy.

## Entry Point Detection

The CLI uses the following entry point resolution:

1. **Explicit specification** - Use `--entry-point filename.py` to specify entry point
2. **Default fallback** - If not specified, defaults to `main.py`

**Entry Point Requirements:**
- Must be a `.py` file
- Must contain `def main(payload):` function with at least one parameter
- Use `--skip-entrypoint-validation` to bypass validation

**Note:** The CLI does not automatically detect single `.py` files. You must either:
- Name your entry point `main.py` (default)
- Explicitly specify with `--entry-point your_script.py`

**Skipping Validation**:

Bypass entry point validation for non-standard workflows:

```bash
act workflow deploy --source-dir /path/to/code --skip-entrypoint-validation
```

**When to Use**:
- Entry point uses dynamic function loading
- Custom parameter signatures beyond `def main(payload):`
- Testing experimental workflow patterns

**Risks**:
- Runtime errors if entry point doesn't match AgentCore expectations
- Harder to debug deployment issues

## IAM Role Management

**Auto-Creation (Default):**
```bash
act workflow deploy --source-dir /path/to/code
# Creates: nova-act-{workflow-name}-role
```

**Use Existing Role:**
```bash
act workflow deploy ... --execution-role-arn "arn:aws:iam::123456789012:role/MyRole"
```

**Auto-created roles include permissions for:**
- Bedrock AgentCore operations
- ECR image access
- CloudWatch Logs
- X-Ray tracing
- S3 access (nova-act-* buckets)

## Region Support

Deploy to different regions with account-based tracking:

```bash
act workflow deploy --name my-workflow --region us-west-2
act workflow run --name my-workflow --region us-west-2
```

Important Note: The AWS Nova Act service is only in us-east-1 as of now!


## AWS Profile Support

Use different AWS profiles from `~/.aws/credentials`:

```bash
# Deploy with specific profile
act workflow --profile <aws_profile_name> deploy --name my-workflow --source-dir /path/to/code

# Run with specific profile
act workflow --profile <aws_profile_name> run --name my-workflow --payload '{}'
```

**Note**: The `--profile` option must come before the subcommand (deploy, run, etc.)

## Environment Variables

Pass environment variables to your workflow at runtime using the `AC_HANDLER_ENV` payload field:

```bash
# Pass NOVA_ACT_API_KEY to workflow
act workflow run --name my-workflow --payload '{
  "AC_HANDLER_ENV": {
    "NOVA_ACT_API_KEY": "your-api-key-here"
  },
  "input": "data"
}'
```

**How It Works**:
1. Include `AC_HANDLER_ENV` dictionary in your payload
2. The AgentCore handler extracts these variables before running your workflow
3. Variables are set in `os.environ` and available to your code

**Benefits**:
- Change configuration without redeploying your AgentCore Runtime
- Pass different credentials per execution
- Test with different settings instantly

**Common Use Cases**:
- `NOVA_ACT_API_KEY` - Nova Act API key for browser automation
- Custom API keys and credentials
- Feature flags and configuration values

**Example Workflow**:
```python
import os

def main(payload):
    api_key = os.environ.get("NOVA_ACT_API_KEY")
    # Use api_key in your workflow
```

## CLI Themes

Customize CLI output styling for different environments.

**Available Themes**:
- `default` - Full color output (default)
- `minimal` - Reduced colors for readability
- `none` - No styling (ideal for CI/CD and automation)

**Set Theme via Environment Variable**:
```bash
export ACT_CLI_THEME=none
act workflow deploy --source-dir /path/to/code
```

**Set Theme in User Config** (`~/.act_cli/config.yml`):
```yaml
theme:
  name: minimal
  enabled: true
```

**Use Cases**:
- `none` theme for CI/CD pipelines and log parsing
- `minimal` theme for terminals with limited color support
- `default` theme for interactive development

## AWS Resources Created

- **ECR Repository**: `nova-act-cli-default` (auto-created, shared across workflows)
- **IAM Role**: `nova-act-{workflow-name}-role` (auto-created unless `--execution-role-arn` provided)
- **S3 Bucket**: `nova-act-{account-id}-{region}` (auto-created unless `--skip-s3-creation` or custom bucket specified)
- **AgentCore Runtime**: Container-based runtime for execution (one per workflow)
- **WorkflowDefinition**: Nova Act Workflow Definition (auto-created via nova-act service)
- **CloudWatch Log Groups**: 
  - `/aws/bedrock-agentcore/runtimes/{agent-id}-default` (runtime logs)
  - `/aws/bedrock-agentcore/runtimes/{agent-id}-default/runtime-logs` (OpenTelemetry logs)

**AWS Console Access**:

After deployment, the CLI provides direct AWS Console links:

```
✓ Workflow deployed successfully
  View in AWS Console: https://console.aws.amazon.com/bedrock/agentcore/...
```

Console links provide access to:
- Bedrock AgentCore Runtime details
- CloudWatch Logs for workflow execution
- ECR repository for container images

## Advanced Options

### Build Configuration
```bash
# Skip building (use existing image)
act workflow deploy --no-build

# Custom build directory
act workflow deploy --build-dir /tmp/my-build

# Custom ECR repository
act workflow deploy --ecr-repo 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo
```

**Build Artifact Preservation**:

Build directories preserve artifacts for debugging or reuse:

```bash
# Use custom build directory
act workflow deploy --source-dir /path/to/code --build-dir /tmp/my-build

# Overwrite existing build directory without prompting
act workflow deploy --source-dir /path/to/code --build-dir /tmp/my-build --overwrite-build-dir
```

**Default Behavior**: 
- Builds are stored in `~/.act_cli/builds/{workflow-name}/`
- Build artifacts are **persistent** and not automatically cleaned up
- Default builds always overwrite previous builds for the same workflow
- Custom build directories require `--overwrite-build-dir` flag to overwrite

### Build Artifact Management

**Default Build Location:**
```bash
~/.act_cli/builds/{workflow-name}/
```

**Cleanup:**
Build artifacts are persistent and not automatically removed. To clean up:

```bash
# Remove specific workflow build
rm -rf ~/.act_cli/builds/my-workflow

# Remove all builds
rm -rf ~/.act_cli/builds/
```

### Execution Options
```bash
# Run with log tailing
act workflow run --name my-workflow --payload '{}' --tail-logs

# Run with payload file
act workflow run --name my-workflow --payload-file payload.json
```

**Log Streaming Details**:

The `--tail-logs` flag streams real-time logs during workflow execution:

**Log Sources**:
- Application logs (stdout/stderr from your workflow)
- OpenTelemetry logs (tracing and instrumentation)

**Log Groups**:
- `/aws/bedrock/agentcore/{agent-id}` - Application logs
- `/aws/bedrock/agentcore/{agent-id}/otel` - OTEL logs

**Behavior**:
- Streams logs in real-time until workflow completes
- Automatically handles log delays and pagination
- Ctrl+C stops tailing but doesn't terminate workflow

### S3 Bucket Configuration

Nova Act workflows may configure S3 buckets for artifact storage. The CLI manages this automatically.

**Default Behavior** (auto-creates bucket):
```bash
act workflow deploy --source-dir /path/to/code
# Creates: nova-act-{account-id}-{region}
```

**Custom Bucket**:
```bash
act workflow deploy --source-dir /path/to/code --s3-bucket-name my-custom-bucket
```

**Skip S3 Creation**:
```bash
act workflow deploy --source-dir /path/to/code --skip-s3-creation
```

**Bucket Requirements**:
- Must be in the same region as the workflow
- Used for workflow definition exports and artifacts

### Workflow Definition Management

Each workflow is backed by a Nova Act WorkflowDefinition resource.

**Automatic Creation** (default):
```bash
act workflow deploy --name my-workflow --source-dir /path/to/code
# Creates WorkflowDefinition automatically
```

**Use Existing WorkflowDefinition**:

To associate an existing WorkflowDefinition with a workflow, use the `create` or `update` commands:

```bash
# During workflow creation
act workflow create --name my-workflow \
  --workflow-definition-arn arn:aws:nova-act:us-east-1:123456789012:workflow-definition/my-workflow

# Or update existing workflow
act workflow update --name my-workflow \
  --workflow-definition-arn arn:aws:nova-act:us-east-1:123456789012:workflow-definition/my-workflow
```

**ARN Format**:
```
arn:aws:nova-act:{region}:{account-id}:workflow-definition/{workflow-name}
```

**Important**: Workflow name must match the name in the ARN. The CLI validates this automatically.

## File Locations

### User Data
- State files: `~/.act_cli/state/{account_id}/{region}/workflows.json` (per region/account)
- User config: `~/.act_cli/config.yml`
- Build artifacts: `~/.act_cli/builds/{workflow-name}/` (persistent)

### Lock Files
- State locks: `~/.act_cli/state/{account_id}-{region}.lock` (temporary, for concurrent access)

## Requirements

- **AWS CLI**: Configured with appropriate permissions
- **Docker**: For building containers  
- **Python 3.10+**: For running the CLI
- **AWS Permissions**: IAM, ECR, AgentCore, STS access

## Troubleshooting

### Docker Build Issues
Ensure Docker is running and accessible:
```bash
docker --version
```

### AWS Authentication
Verify AWS credentials and account access:
```bash
aws sts get-caller-identity
```

### ECR Login Issues
The CLI handles ECR authentication automatically, but you can manually refresh:
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin {account-id}.dkr.ecr.us-east-1.amazonaws.com
```

### Entry Point Validation
If your entry point doesn't follow the expected pattern:
```bash
act workflow deploy --skip-entrypoint-validation --source-dir /path/to/code
```

### Common Error Scenarios

The CLI detects common issues and provides actionable guidance:

**Credential Errors**:
```
Error: AWS credentials not configured
→ Run: aws configure
→ Or set: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
```

**Permission Errors**:
```
Error: Missing IAM permission: ecr:CreateRepository
→ Required for: Creating ECR repository for workflow images
→ Add policy: AmazonEC2ContainerRegistryFullAccess
→ Or create repository manually with --ecr-repo
```

**Docker Not Running**:
```
Error: Docker daemon not accessible
→ Start Docker Desktop or Docker service
→ Verify: docker ps
```

**Entry Point Validation Errors**:
```
Error: Entry point missing main() function
→ Add: def main(payload): ...
→ Or use: --skip-entrypoint-validation
```

## AWS Permissions

The CLI requires permissions across multiple AWS services. Choose the appropriate policy based on your use case.

### Complete Policy (All Features)

For full CLI functionality including deployment and execution:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "STSIdentityVerification",
      "Effect": "Allow",
      "Action": ["sts:GetCallerIdentity"],
      "Resource": "*"
    },
    {
      "Sid": "IAMRoleManagement",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:GetRole",
        "iam:PutRolePolicy",
        "iam:AttachRolePolicy"
      ],
      "Resource": "arn:aws:iam::*:role/nova-act-*"
    },
    {
      "Sid": "ECRRepositoryManagement",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:DescribeRepositories",
        "ecr:CreateRepository"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECRImageOperations",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage"
      ],
      "Resource": "arn:aws:ecr:*:*:repository/*"
    },
    {
      "Sid": "S3BucketManagement",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:HeadBucket",
        "s3:GetBucketLocation",
        "s3:ListBucket",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutBucketEncryption",
        "s3:GetBucketEncryption",
        "s3:PutBucketVersioning",
        "s3:GetBucketVersioning",
        "s3:ListAllMyBuckets"
      ],
      "Resource": "arn:aws:s3:::nova-act-*"
    },
    {
      "Sid": "S3ObjectOperations",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::nova-act-*/*"
    },
    {
      "Sid": "BedrockAgentCoreControl",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:CreateAgentRuntime",
        "bedrock-agentcore:UpdateAgentRuntime",
        "bedrock-agentcore:ListAgentRuntimes"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BedrockAgentCoreData",
      "Effect": "Allow",
      "Action": ["bedrock-agentcore:InvokeAgentRuntime"],
      "Resource": "*"
    },
    {
      "Sid": "NovaActWorkflowDefinitions",
      "Effect": "Allow",
      "Action": [
        "nova-act:CreateWorkflowDefinition",
        "nova-act:GetWorkflowDefinition",
        "nova-act:DeleteWorkflowDefinition"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CloudWatchLogsStreaming",
      "Effect": "Allow",
      "Action": [
        "logs:StartLiveTail",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "*"
    }
  ]
}
```

### Minimal Policy (Run Workflows Only)

For users who only need to execute existing workflows:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity",
        "bedrock-agentcore:InvokeAgentRuntime",
        "logs:StartLiveTail",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "*"
    }
  ]
}
```

### Developer Policy (Deploy Without IAM Role Creation)

For developers who deploy workflows but use pre-created execution roles:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["sts:GetCallerIdentity"],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": ["iam:GetRole"],
      "Resource": "arn:aws:iam::*:role/nova-act-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:DescribeRepositories",
        "ecr:CreateRepository",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:HeadBucket",
        "s3:GetBucketLocation",
        "s3:ListBucket",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutBucketEncryption",
        "s3:GetBucketEncryption",
        "s3:PutBucketVersioning",
        "s3:GetBucketVersioning",
        "s3:ListAllMyBuckets",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": ["arn:aws:s3:::nova-act-*", "arn:aws:s3:::nova-act-*/*"]
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:CreateAgentRuntime",
        "bedrock-agentcore:UpdateAgentRuntime",
        "bedrock-agentcore:ListAgentRuntimes",
        "bedrock-agentcore:InvokeAgentRuntime"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "nova-act:CreateWorkflowDefinition",
        "nova-act:GetWorkflowDefinition",
        "nova-act:DeleteWorkflowDefinition"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:StartLiveTail",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "*"
    }
  ]
}
```

**Usage**: Provide existing role with `--execution-role-arn` flag:
```bash
act workflow deploy --source-dir /path/to/code \
  --execution-role-arn arn:aws:iam::123456789012:role/my-execution-role
```

### Permission Requirements by Command

| Command | Required Permissions |
|---------|---------------------|
| `create` | STS, Nova Act, S3 (unless `--skip-s3-creation`) |
| `deploy` | STS, IAM (unless `--execution-role-arn`), ECR, S3, Bedrock AgentCore, Nova Act |
| `run` | STS, Bedrock AgentCore |
| `run --tail-logs` | STS, Bedrock AgentCore, CloudWatch Logs |
| `list` | STS only |
| `show` | STS only |
| `update` | STS, Nova Act |
| `delete` | STS only |

### Resource Naming Patterns

The CLI creates AWS resources with predictable naming:

| Resource | Pattern | Example |
|----------|---------|---------|
| IAM Role | `nova-act-{workflow-name}-role` | `nova-act-my-workflow-role` |
| ECR Repository | `nova-act-cli-default` | `nova-act-cli-default` |
| S3 Bucket | `nova-act-{account-id}-{region}` | `nova-act-123456789012-us-east-1` |
| CloudWatch Log Group | `/aws/bedrock-agentcore/{agent-id}-{endpoint}` | `/aws/bedrock-agentcore/ABC123-default` |
| CloudWatch Runtime Logs | `/aws/bedrock-agentcore/runtimes/{agent-id}-default` | `/aws/bedrock-agentcore/runtimes/ABC123-default` |
| CloudWatch OTEL Logs | `/aws/bedrock-agentcore/runtimes/{agent-id}-default/runtime-logs` | `/aws/bedrock-agentcore/runtimes/ABC123-default/runtime-logs` |
