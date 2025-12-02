# Nova Act CLI Codebase Structure

## What This CLI Does

The Nova Act CLI is a Python command-line tool that deploys Python workflows to AWS AgentCore Runtime. It handles containerization, AWS service integration, and workflow lifecycle management.

**Core Capabilities:**
- Deploy Python scripts to AWS AgentCore with automatic containerization
- Manage ECR repositories and Docker images
- Track workflow state across multiple AWS regions and accounts
- Run workflows and stream logs in real-time
- Handle workflow creation, deployment, execution, and deletion

## Current Codebase Structure

### Directory Organization

```
cli/
├── __init__.py              # Package initialization
├── __version__.py           # Version information
├── CODEBASE.md             # This documentation file
├── README.md               # User documentation
├── cli.py                  # Main CLI entry point
├── group.py                # Custom Click group with styled help
├── core/                   # Core infrastructure components
│   ├── __init__.py         # Core package initialization
│   ├── config.py           # Configuration path utilities
│   ├── constants.py        # Application constants
│   ├── error_detection.py  # Error detection and user-friendly messages
│   ├── exceptions.py       # Custom exception classes
│   ├── identity.py         # AWS identity resolution
│   ├── logging.py          # Logging configuration
│   ├── region.py           # AWS region utilities
│   ├── state_manager.py    # Per-region state management
│   ├── styling.py          # CLI output styling
│   ├── theme.py            # Theme system for CLI styling
│   ├── types.py            # Core type definitions
│   ├── user_config_manager.py # User configuration management
│   └── clients/            # AWS service clients
│       ├── __init__.py     # Clients package initialization
│       ├── agentcore/      # AWS AgentCore service client
│       │   ├── __init__.py
│       │   ├── client.py   # AgentCore API client
│       │   ├── constants.py # AgentCore constants
│       │   ├── response_parser.py # Response parsing utilities
│       │   └── types.py    # AgentCore type definitions
│       ├── ecr/            # AWS ECR service client
│       │   ├── __init__.py
│       │   ├── client.py   # ECR API client
│       │   └── constants.py # ECR constants
│       ├── iam/            # AWS IAM service client
│       │   ├── __init__.py
│       │   ├── client.py   # IAM API client
│       │   └── types.py    # IAM type definitions
│       ├── nova_act/       # Nova Act service client
│       │   ├── __init__.py
│       │   ├── client.py   # Nova Act API client
│       │   ├── constants.py # Nova Act constants
│       │   └── types.py    # Nova Act type definitions
│       └── s3/             # AWS S3 service client
│           ├── __init__.py
│           └── client.py   # S3 API client
└── workflow/               # Workflow management system
    ├── __init__.py         # Workflow package initialization
    ├── commands/           # CLI command implementations
    │   ├── __init__.py     # Commands package initialization
    │   ├── create.py       # Workflow creation
    │   ├── delete.py       # Workflow deletion
    │   ├── deploy.py       # Workflow deployment
    │   ├── list.py         # Workflow listing
    │   ├── run.py          # Workflow execution
    │   ├── show.py         # Workflow information display
    │   └── update.py       # Workflow updates
    ├── services/           # External service integrations
    │   ├── __init__.py     # Services package initialization
    │   ├── constants.py    # Service constants
    │   └── agentcore/      # AgentCore workflow services
    │       ├── __init__.py
    │       ├── deployment_service.py # AgentCore deployment orchestration
    │       ├── iam_role.py # IAM role management for AgentCore
    │       ├── image_builder.py # AgentCore workflow builder
    │       ├── source_validator.py # Source validation utilities
    │       └── templates/  # Docker build templates
    │           ├── Dockerfile
    │           ├── requirements.txt
    │           ├── agentcore_handler.py
    │           └── wheels/ # Pre-built wheel dependencies
    ├── utils/              # Workflow utilities
    │   ├── __init__.py     # Utils package initialization
    │   ├── arn.py          # ARN validation utilities
    │   ├── bucket_manager.py # S3 bucket management
    │   ├── console.py      # AWS Console URL utilities
    │   ├── docker_builder.py # Generic Docker build operations
    │   ├── log_tailer.py   # CloudWatch log tailing
    │   └── tags.py         # AWS resource tagging
    ├── workflow_deployer.py # Centralized deployment logic
    └── workflow_manager.py  # Workflow CRUD operations
```

## File Interfaces and Components

### CLI Entry Points

#### cli.py
**Purpose:** Main CLI entry point defining command groups and subcommands
**Interface:**
```python
@click.group(cls=StyledGroup)
def workflow() -> None
    # Main workflow command group

@click.group(cls=StyledGroup)
@click.version_option(version=VERSION)
def main() -> None
    # Nova Act CLI main entry point
```

#### group.py
**Purpose:** Custom Click group for styled help output
**Interface:**
```python
class StyledGroup(click.Group):
    def format_help(ctx: click.Context, formatter: click.HelpFormatter) -> None
    def format_usage(ctx: click.Context, formatter: click.HelpFormatter) -> None
```

### Core Infrastructure (core/)

#### core/config.py
**Purpose:** Configuration path utilities for regional workflow support
**Interface:**
```python
def get_cli_config_dir() -> Path
def get_state_dir() -> Path
def get_account_dir(account_id: str) -> Path
def get_region_dir(account_id: str, region: str) -> Path
def get_state_file_path(account_id: str, region: str) -> Path
def get_cli_config_file_path() -> Path
```

#### core/constants.py
**Purpose:** Application-wide constants
**Interface:**
```python
CONFIG_DIR_NAME: str
BUILD_TEMP_DIR: str
DEFAULT_ENTRY_POINT: str

# Theme configuration
DEFAULT_THEME: ThemeName
THEME_ENV_VAR: str = "ACT_CLI_THEME"

# Console deep link configuration
CONSOLE_WORKFLOW_DEFINITIONS_URL: str

# Other application constants
```

#### core/exceptions.py
**Purpose:** Custom exception hierarchy for Nova Act CLI
**Interface:**
```python
class NovaActCLIError(Exception)           # Base exception
class ValidationError(NovaActCLIError)     # Input validation failures
class DeploymentError(NovaActCLIError)     # Deployment operation failures
class ConfigurationError(NovaActCLIError)  # Configuration issues
class WorkflowError(NovaActCLIError)       # Workflow operation failures
class WorkflowNameArnMismatchError(WorkflowError)  # Workflow name/ARN mismatch
class RuntimeError(NovaActCLIError)        # Runtime operation failures
class ImageBuildError(NovaActCLIError)     # ECR image build failures
```

#### core/identity.py
**Purpose:** AWS identity resolution utilities
**Interface:**
```python
def auto_detect_account_id(region: str) -> str
def validate_iam_role_arn(role_arn: str) -> bool
def extract_role_name_from_arn(role_arn: str) -> str
```

#### core/logging.py
**Purpose:** Logging configuration for the CLI
**Interface:**
```python
# Logging setup and configuration utilities
```

#### core/region.py
**Purpose:** AWS region utilities
**Interface:**
```python
DEFAULT_REGION: str = "us-east-1"
def get_default_region() -> str
```

#### core/state_manager.py
**Purpose:** Per-region workflow state management with file locking
**Interface:**
```python
class StateLock:
    def __init__(account_id: str, region: str)
    def __enter__() -> "StateLock"
    def __exit__(exc_type, exc_val, exc_tb) -> None

class StateManager:
    def __init__(account_id: str, region: str)
    def get_region_state() -> RegionState
    def save_region_state(state: RegionState) -> None
    def add_workflow(workflow: WorkflowInfo) -> None
    def update_workflow(workflow: WorkflowInfo) -> None
    def remove_workflow(name: str) -> None
    def list_workflows() -> List[WorkflowInfo]
    def cleanup_account() -> None
    def cleanup_region() -> None
```

#### core/styling.py
**Purpose:** CLI output styling using Click's built-in styling
**Interface:**
```python
def success(message: str) -> None
def warning(message: str) -> None
def error(message: str) -> None
def info(message: str) -> None
def header(text: str) -> str
def value(text: str) -> str
def secondary(text: str) -> str
def command(text: str) -> str
def styled_error_exception(message: str) -> click.ClickException

# Note: Now uses theme system via get_active_theme()
# Initializes theme from config or environment via _initialize_theme()
```

#### core/types.py
**Purpose:** Core type definitions using Pydantic models
**Interface:**
```python
class ServiceDeployment(BaseModel):
    deployment_arn: str
    image_uri: str

class AgentCoreDeployment(BaseModel):
    deployment_arn: str
    image_uri: str
    image_tag: str

class WorkflowDeployments(BaseModel):
    agentcore: AgentCoreDeployment | None = None

class WorkflowInfo(BaseModel):
    name: str
    directory_path: str
    created_at: datetime
    workflow_definition_arn: str | None = None
    deployments: WorkflowDeployments
    metadata: Dict[str, str] | None = None
    last_image_tag: str | None = None

class BuildConfig(BaseModel):
    default_entry_point: str = DEFAULT_ENTRY_POINT
    temp_dir: str = BUILD_TEMP_DIR

class ThemeConfig(BaseModel):
    name: str = "default"
    enabled: bool = True

class UserConfig(BaseModel):
    build: BuildConfig
    theme: ThemeConfig

class RegionState(BaseModel):
    workflows: Dict[str, WorkflowInfo]
    last_updated: datetime
    version: str = "1.0"

class StateLockInfo(BaseModel):
    lock_file: str
    timeout: int = 30

class RegionContext(BaseModel):
    region: str
    account_id: str
```

#### core/user_config_manager.py
**Purpose:** User configuration management in YAML format
**Interface:**
```python
class UserConfigManager:
    def __init__()
    def get_config() -> UserConfig
    def save_config(config: UserConfig) -> None
```

#### core/theme.py
**Purpose:** Theme system for CLI styling with multiple theme options
**Interface:**
```python
class ThemeName(str, Enum):
    DEFAULT = "default"
    MINIMAL = "minimal"
    NONE = "none"

class Theme(Protocol):
    enabled: bool
    def apply_info(text: str) -> str
    def apply_success(text: str) -> str
    def apply_error(text: str) -> str
    def apply_warning(text: str) -> str
    def apply_header(text: str) -> str
    def apply_value(text: str) -> str
    def apply_secondary(text: str) -> str
    def apply_command(text: str) -> str

class DefaultTheme:
    """Default color theme matching current CLI appearance"""
    enabled: bool = True
    # Implements all Theme protocol methods with colors

class MinimalTheme:
    """Minimal theme with reduced colors"""
    enabled: bool = True
    # Implements all Theme protocol methods with minimal styling

class NoTheme:
    """No styling theme for automation/scripting"""
    enabled: bool = False
    # Implements all Theme protocol methods returning plain text

def get_theme(name: str | ThemeName) -> Theme
def set_active_theme(theme_name: ThemeName) -> None
def get_active_theme() -> Theme
```

#### core/error_detection.py
**Purpose:** Error detection and user-friendly error message generation
**Interface:**
```python
# Error Detection Functions
def is_credential_error(error: Exception) -> bool
def is_permission_error(error: Exception) -> bool
def extract_permission_from_error(error: ClientError) -> str | None
def extract_operation_name(error: ClientError) -> str
def is_docker_running() -> bool

# User-Friendly Error Message Generators
def get_credential_error_message() -> str
def get_permission_error_message(operation: str, workflow_name: str, region: str, account_id: str, permission: str | None = None) -> str
def get_docker_not_running_message() -> str
def get_docker_build_failed_message(build_path: str) -> str
def get_entry_point_missing_main_message(entry_point_path: Path) -> str
def get_entry_point_missing_parameter_message(entry_point_path: Path) -> str
def get_workflow_not_found_message(name: str, region: str, account_id: str, available_workflows: list[str]) -> str
def get_state_corrupted_message(state_file: Path, error: str) -> str
def get_state_write_failed_message(state_file: Path, error: str) -> str
```

### AWS Service Clients (core/clients/)

#### core/clients/agentcore/client.py
**Purpose:** AgentCore service operations client
**Interface:**
```python
class AgentCoreClient:
    def __init__(region: str)
    def create_agent_runtime(request: CreateAgentRuntimeRequest) -> CreateAgentRuntimeResponse
    def update_agent_runtime(request: UpdateAgentRuntimeRequest) -> UpdateAgentRuntimeResponse
    def list_agent_runtimes(request: ListAgentRuntimesRequest) -> ListAgentRuntimesResponse
    def delete_agent_runtime(agent_runtime_arn: str) -> None
    def invoke_agent_runtime(request: InvokeAgentRuntimeRequest) -> InvokeAgentRuntimeResponse
    def get_agent_log_groups(agent_arn: str) -> Tuple[str, str]
    def generate_agent_name(workflow_name: str) -> str
```

#### core/clients/agentcore/constants.py
**Purpose:** AgentCore service constants
**Interface:**
```python
AGENT_NAME_PREFIX: str
MAX_AGENT_NAME_LENGTH: int
BEDROCK_AGENT_CONTROL_SERVICE: str
BEDROCK_AGENT_DATA_SERVICE: str
DEFAULT_ENDPOINT_NAME: str
LOG_GROUP_PREFIX: str
OTEL_LOG_SUFFIX: str
PUBLIC_NETWORK_MODE: str
ALREADY_EXISTS_ERROR: str
CONFLICT_ERROR: str
```

#### core/clients/agentcore/response_parser.py
**Purpose:** AgentCore response parsing utilities
**Interface:**
```python
def parse_invoke_response(response_stream) -> str
```

#### core/clients/agentcore/types.py
**Purpose:** AgentCore type definitions
**Interface:**
```python
class ContainerConfiguration(BaseModel)
class AgentRuntimeArtifact(BaseModel)
class AgentRuntimeConfig(BaseModel)
class AgentRuntimeSummary(BaseModel)
class CreateAgentRuntimeRequest(BaseModel)
class CreateAgentRuntimeResponse(BaseModel)
class UpdateAgentRuntimeRequest(BaseModel)
class UpdateAgentRuntimeResponse(BaseModel)
class ListAgentRuntimesRequest(BaseModel)
class ListAgentRuntimesResponse(BaseModel)
class InvokeAgentRuntimeRequest(BaseModel)
class InvokeAgentRuntimeResponse(BaseModel)
```

#### core/clients/ecr/client.py
**Purpose:** ECR service operations client
**Interface:**
```python
class ECRClient:
    def __init__(region: str)
    def check_repository_exists(repository_uri: str) -> bool
    def create_default_repository() -> str
    def get_authorization_token() -> str
    def docker_login() -> None
    def push_image(image_tag: str, repository_uri: str) -> str
```

#### core/clients/ecr/constants.py
**Purpose:** ECR service constants
**Interface:**
```python
DEFAULT_REPOSITORY_NAME: str
```

#### core/clients/nova_act/client.py
**Purpose:** Nova Act service operations client
**Interface:**
```python
class NovaActClient:
    def __init__(boto_session: boto3.Session, endpoint_url: str, region_name: str)
    def create_workflow_definition(request: CreateWorkflowDefinitionRequest) -> CreateWorkflowDefinitionResponse
    def get_workflow_definition(workflow_definition_name: str) -> GetWorkflowDefinitionResponse
    def delete_workflow_definition(workflow_definition_name: str) -> None
```

#### core/clients/nova_act/constants.py
**Purpose:** Nova Act service constants
**Interface:**
```python
DEFAULT_ENDPOINT_URL: str
SERVICE_NAME: str
```

#### core/clients/nova_act/types.py
**Purpose:** Nova Act type definitions
**Interface:**
```python
class CreateWorkflowDefinitionRequest(BaseModel)
class CreateWorkflowDefinitionResponse(BaseModel)
class GetWorkflowDefinitionResponse(BaseModel)
class WorkflowDefinition(BaseModel)
```

#### core/clients/iam/client.py
**Purpose:** IAM service operations client
**Interface:**
```python
class IAMClient:
    def __init__(region: str)
    def get_role(role_name: str) -> GetRoleResponse
    def create_role(role_name: str, assume_role_policy_document: str, description: str | None = None) -> CreateRoleResponse
    def attach_role_policy(role_name: str, policy_arn: str) -> None
    def role_exists(role_name: str) -> bool
```

#### core/clients/iam/types.py
**Purpose:** IAM type definitions
**Interface:**
```python
class Role(BaseModel)
class GetRoleResponse(BaseModel)
class CreateRoleResponse(BaseModel)
```

#### core/clients/s3/client.py
**Purpose:** S3 service operations client
**Interface:**
```python
class S3Client:
    def __init__(region: str)
    def bucket_exists(bucket_name: str) -> bool
    def get_bucket_location(bucket_name: str) -> str
    def create_bucket(bucket_name: str) -> None
```

### Workflow Management (workflow/)

#### workflow/workflow_deployer.py
**Purpose:** Centralized workflow deployment orchestration
**Interface:**
```python
class WorkflowDeployer:
    def __init__(
        region: str,
        account_id: Optional[str] = None,
        execution_role_arn: str | None = None,
        workflow_name: str | None = None,
        source_dir: str | None = None,
        entry_point: str | None = None,
        ecr_repo: str | None = None,
        no_build: bool = False,
        skip_entrypoint_validation: bool = False,
        build_dir: str | None = None,
        overwrite_build_dir: bool = False,
        s3_bucket_name: str | None = None,
        skip_s3_creation: bool = False,
    )
    def deploy_workflow(request: DeploymentRequest) -> WorkflowInfo
    def quick_deploy(source_path: str, entry_point: Optional[str] = None, **kwargs) -> WorkflowInfo
```

#### workflow/workflow_manager.py
**Purpose:** Workflow CRUD operations and lifecycle management
**Interface:**
```python
class WorkflowManager:
    def __init__(region: str, account_id: str)
    
    # Core CRUD operations
    def create_workflow(name: str, workflow_definition_arn: str | None = None) -> WorkflowInfo
    def update_workflow(name: str, **kwargs) -> WorkflowInfo
    def delete_workflow(name: str) -> None
    def get_workflow(name: str) -> WorkflowInfo
    def list_workflows() -> Dict[str, WorkflowInfo]
    
    # WorkflowDefinition management
    def create_workflow_with_definition(name: str, provided_arn: str | None = None, s3_bucket_name: str | None = None, skip_s3_creation: bool = False) -> WorkflowInfo
    def update_workflow_definition_arn(name: str, workflow_definition_arn: str) -> WorkflowInfo
    def create_workflow_definition(name: str, description: str | None = None, s3_bucket_name: str | None = None, skip_s3_creation: bool = False) -> str
    
    # Deployment support
    def ensure_workflow_for_deployment(name: str | None, s3_bucket_name: str | None, skip_s3_creation: bool) -> str
    def update_deployment_state(workflow_name: str, agentcore_deployment: AgentCoreDeployment, source_dir: str | None = None) -> None
    
    # Internal helpers
    def _ensure_workflow_definition_exists(name: str, s3_bucket_name: str | None, skip_s3_creation: bool) -> str | None
    def _recover_workflow_definition_if_needed(workflow: WorkflowInfo, s3_bucket_name: str | None, skip_s3_creation: bool) -> WorkflowInfo
    def _extract_resource_name_from_arn(arn: str) -> str
    def _validate_workflow_name_matches_arn(workflow_name: str, arn: str) -> None
    def _validate_workflow_definition_exists(workflow_definition_arn: str) -> None
    def _create_export_config(custom_bucket_name: str | None = None) -> ExportConfig | None
    def _register_temporary_workflow(workflow_name: str, s3_bucket_name: str | None, skip_s3_creation: bool) -> None
    def _create_workflow_with_s3(workflow_name: str, s3_bucket_name: str | None) -> None

# Module-level validation
def validate_workflow_name(name: str) -> None
```

### CLI Commands (workflow/commands/)

#### workflow/commands/create.py
**Purpose:** Workflow creation command implementation
**Interface:**
```python
@click.command()
@click.option('--name', required=True)
@click.option('--region')
def create(name: str, region: Optional[str]) -> None
```

#### workflow/commands/deploy.py
**Purpose:** Workflow deployment command implementation
**Interface:**
```python
@click.command()
@click.option('--name')
@click.option('--source-dir')
@click.option('--entry-point')
@click.option('--region')
@click.option('--build-dir')
@click.option('--force', is_flag=True)
@click.option('--no-build', is_flag=True)
def deploy(name: Optional[str], source_dir: Optional[str], **kwargs) -> None
```

#### workflow/commands/run.py
**Purpose:** Workflow execution command implementation
**Interface:**
```python
@click.command()
@click.option('--name', required=True)
@click.option('--payload')
@click.option('--payload-file')
@click.option('--tail-logs', is_flag=True)
@click.option('--region')
def run(name: str, payload: Optional[str], **kwargs) -> None
```

#### workflow/commands/delete.py
**Purpose:** Workflow deletion command implementation
**Interface:**
```python
@click.command()
@click.option('--name', required=True)
@click.option('--force', is_flag=True)
@click.option('--region')
def delete(name: str, force: bool, region: Optional[str]) -> None
```

#### workflow/commands/list.py
**Purpose:** Workflow listing command implementation
**Interface:**
```python
@click.command()
@click.option('--region')
@click.option('--format', type=click.Choice(['table', 'json']))
def list_workflows(region: Optional[str], format: str) -> None
```

#### workflow/commands/show.py
**Purpose:** Workflow information display command implementation
**Interface:**
```python
@click.command()
@click.option('--name', required=True)
@click.option('--region')
@click.option('--format', type=click.Choice(['table', 'json']))
def show(name: str, region: Optional[str], format: str) -> None
```

#### workflow/commands/update.py
**Purpose:** Workflow update command implementation
**Interface:**
```python
@click.command()
@click.option('--name', required=True)
@click.option('--source-dir')
@click.option('--entry-point')
@click.option('--region')
def update(name: str, **kwargs) -> None
```

### Workflow Services (workflow/services/)

#### workflow/services/agentcore/deployment_service.py
**Purpose:** AgentCore deployment orchestration service
**Interface:**
```python
class AgentCoreDeploymentService:
    def __init__(agent_name: str, execution_role_arn: str | None, region: str, account_id: str, **kwargs)
    def deploy() -> AgentCoreDeployment
```

#### workflow/services/agentcore/iam_role.py
**Purpose:** IAM role management for AgentCore workflows
**Interface:**
```python
class AgentCoreIAMRoleManager:
    def __init__(region: str)
    def ensure_execution_role(workflow_name: str) -> str
    def get_default_role_name(workflow_name: str) -> str
```

#### workflow/services/agentcore/image_builder.py
**Purpose:** AgentCore workflow builder with Docker containerization
**Interface:**
```python
class AgentCoreImageBuilder:
    def __init__(workflow_name: str, project_path: str, entry_point: str)
    def build_workflow_image(build_dir: Optional[str] = None, force: bool = False) -> str
```

#### workflow/services/agentcore/source_validator.py
**Purpose:** AgentCore-specific source validation utilities
**Interface:**
```python
class AgentCoreSourceValidator:
    def __init__(source_dir: str, entry_point: str | None = None, skip_validation: bool = False)
    def validate() -> None
    
    # Properties:
    source_path: Path
    entry_point: str
    skip_validation: bool

def validate_entry_point_file(entry_point_path: str) -> None
```

### Workflow Utilities (workflow/utils/)

#### workflow/utils/arn.py
**Purpose:** ARN validation utilities
**Interface:**
```python
def validate_workflow_definition_arn(arn: str) -> None
def construct_workflow_definition_arn(workflow_name: str, region: str, account_id: str) -> str
```

#### workflow/utils/bucket_manager.py
**Purpose:** High-level S3 bucket management for Nova Act workflows
**Interface:**
```python
class BucketManager:
    def __init__(region: str, account_id: str)
    def ensure_default_bucket() -> str
    def generate_default_nova_act_bucket_name() -> str
```

#### workflow/utils/docker_builder.py
**Purpose:** Generic Docker build operations
**Interface:**
```python
class DockerBuilder:
    def __init__(image_tag: str, build_dir: str | None = None, force: bool = False)
    def build(project_path: str, template_dir: Path) -> str
```

#### workflow/utils/log_tailer.py
**Purpose:** Log tailing functionality for AgentCore workflows
**Interface:**
```python
class LogEvent:
    message: str
    timestamp: int

class LogTailer:
    def __init__(region: str, log_group: str)
    def start(callback: Callable[[LogEvent], None]) -> None
    def stop() -> None
```

#### workflow/utils/console.py
**Purpose:** AWS Console URL utilities
**Interface:**
```python
def build_bedrock_agentcore_console_url(region: str, agent_id: str) -> str
```

#### workflow/utils/tags.py
**Purpose:** AWS resource tagging utilities
**Interface:**
```python
WORKFLOW_TAG_KEY: str = "nova-act-workflow-definition-v1"
def generate_workflow_tags(workflow_name: str) -> Dict[str, str]
```

## How Components Work Together

### CLI Command Flow
1. **cli.py** defines main command groups and registers subcommands
2. **group.py** provides styled help output and usage examples
3. **workflow/commands/*.py** implement individual CLI commands using core components

### Deployment Process
1. **AgentCoreSourceValidator** validates source directory and entry point
2. **WorkflowDeployer** orchestrates the deployment:
   - Uses **AgentCoreDeploymentService** for AgentCore-specific deployment
   - Uses **AgentCoreImageBuilder** to build container images
   - Uses **ECRClient** to push images to ECR
   - Uses **AgentCoreClient** to create agent runtime
   - Uses **StateManager** to persist workflow state
3. **BucketManager** ensures S3 buckets exist for artifacts
4. **AgentCoreIAMRoleManager** manages IAM roles for execution

### State Management
- **StateManager** handles per-region JSON state files with file locking
- **StateLock** provides concurrent access protection
- Files stored in `~/.act_cli/state/{account_id}-{region}.json`
- **UserConfigManager** handles YAML-based user preferences

### Service Integration
- **AgentCoreClient** manages workflow runtime environments
- **ECRClient** handles Docker image registry operations
- **S3Client** manages bucket operations for artifacts
- **NovaActClient** manages workflow definitions
- **IAMClient** manages IAM roles and policies

### Validation and Utilities
- **AgentCoreSourceValidator** ensures source files meet requirements
- **WorkflowManager** provides full CRUD operations for workflows
- **LogTailer** streams CloudWatch logs in real-time
- **ARN utilities** validate and construct AWS resource identifiers
- **Console utilities** generate AWS Console URLs for resources

## Key Data Flow

1. **CLI Input:** Click commands → parameter validation
2. **Input Validation:** AgentCoreSourceValidator → validated source files
3. **IAM Setup:** AgentCoreIAMRoleManager → execution role
4. **Image Building:** AgentCoreImageBuilder → container image
5. **Image Storage:** ECRClient → ECR repository
6. **Runtime Creation:** AgentCoreDeploymentService → AgentCore runtime
7. **State Persistence:** StateManager → JSON state files
8. **Log Streaming:** LogTailer → real-time log output

## Command Reference

### Available Commands
- `act workflow create` - Create workflow definition
- `act workflow deploy` - Deploy workflow to AWS
- `act workflow run` - Execute deployed workflow
- `act workflow delete` - Remove workflow and AWS resources
- `act workflow list` - Show all workflows in region
- `act workflow show` - Display workflow details
- `act workflow update` - Modify workflow settings

### Common Options
- `--region` - AWS region (defaults to current AWS CLI region)
- `--name` - Workflow definition name for named deployments
- `--source-dir` - Local directory containing Python workflow
- `--entry-point` - Specific Python entry point file
- `--role-arn` - Custom IAM role ARN (optional)
- `--force` - Force operations that might be destructive
- `--tail-logs` - Stream logs during workflow execution

## Dependencies

### AWS Services Used
- **Bedrock AgentCore** - Runtime environment for workflows
- **ECR** - Container registry for Docker images
- **S3** - Storage for workflow artifacts
- **CloudWatch Logs** - Runtime logging
- **STS** - AWS identity resolution
- **IAM** - Role and policy management

### Python Libraries
- **Pydantic** - Type-safe data structures
- **Boto3** - AWS SDK
- **Click** - CLI framework (for styling)
- **PyYAML** - Configuration files
- **Docker** - Container operations

### External Dependencies
- **Docker Daemon** - Local container building
- **Nova Act API** - Workflow definition management
