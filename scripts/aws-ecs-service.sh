#!/bin/bash

AWS=$(which aws)
JQ=$(which jq)

CLUSTER_NAME="green-detective"
SERVICE_NAME=""
SHELL_TYPE="bash"

_check_libs() {
  if [ -z ${AWS} ]; then
    echo "aws-cli is required to run this script. Please install it and try again."
    exit 1
  fi

  if [ -z ${JQ} ]; then
    echo "jq is required to run this script. Please install it and try again."
    exit 1
  fi
}

_has_argument() {
  [[ ("$1" == *=* && -n ${1#*=}) || (! -z "$2" && "$2" != -*) ]]
}

_extract_argument() {
  echo "${2:-${1#*=}}"
}

_handle_opts() {
  while [ $# -gt 0 ]; do
    case $1 in
    -h | --help)
      help
      exit 0
      ;;
    -f | --func*)
      if ! _has_argument $@; then
        echo "Function not specified." >&2
        help
        exit 1
      fi
      FUNCTION_NAME=$(_extract_argument $@)
      shift
      ;;
    -c | --cluster)
      if ! _has_argument $@; then
        echo "Cluster not specified." >&2
        help
        exit 1
      fi
      CLUSTER_NAME=$(_extract_argument $@)
      shift
      ;;
    -s | --service*)
      if ! _has_argument $@; then
        echo "Service name not specified." >&2
        help
        exit 1
      fi
      SERVICE_NAME=$(_extract_argument $@)
      shift
      ;;
    --shell-type*)
      if ! _has_argument $@; then
        echo "Shell type not specified." >&2
        help
        exit 1
      fi
      SHELL_TYPE=$(_extract_argument $@)
      shift
      ;;
    *)
      echo "Invalid option: $1" >&2
      help
      exit 1
      ;;
    esac
    shift
  done
}

_process_cmd() {
  if [ ${FUNCTION_NAME} ]; then
    ${FUNCTION_NAME}
  fi
}

# AWS functions
# Common functions
_valify_cluster_name() {
  if [ -z ${CLUSTER_NAME} ]; then
    echo "Cluster name is required."
    exit 1
  fi
}

_valify_service_name() {
  if [ -z ${SERVICE_NAME} ]; then
    echo "Service name is required."
    exit 1
  fi
}

# Actual function
get_arn() {
  _valify_cluster_name
  _valify_service_name

  aws ecs describe-services \
    --cluster=${CLUSTER_NAME} \
    --services=${SERVICE_NAME} \
    --profile default |
    jq '.services[0].serviceArn' --raw-output
}

get_conatiner_arn() {
  _valify_cluster_name
  _valify_service_name

  TASK_ARN=$(get_task_arn)
  aws ecs describe-tasks \
    --cluster=${CLUSTER_NAME} \
    --tasks=${TASK_ARN} \
    --profile default |
    jq '.tasks[0].containers[0].name' --raw-output
}

get_task_arn() {
  _valify_cluster_name
  _valify_service_name

  aws ecs list-tasks \
    --cluster=${CLUSTER_NAME} \
    --service-name=${SERVICE_NAME} \
    --profile default |
    jq '.taskArns[0]' --raw-output
}

get_task_def() {
  _valify_cluster_name
  _valify_service_name

  aws ecs describe-services \
    --cluster=${CLUSTER_NAME} \
    --services=${SERVICE_NAME} \
    --profile default |
    jq '.services[0].taskDefinition' --raw-output
}

is_execute_command_enabled() {
  _valify_cluster_name
  _valify_service_name

  TASK_ARN=$(get_task_arn)
  aws ecs describe-tasks \
    --cluster=${CLUSTER_NAME} \
    --tasks=${TASK_ARN} \
    --profile default |
    jq '.tasks[0].enableExecuteCommand'
}

enable_execute_command() {
  _valify_cluster_name
  _valify_service_name

  ENABLED=$(is_execute_command_enabled)
  if [ "${ENABLED}" == "true" ]; then
    echo "Execute command is already enabled for ${SERVICE_NAME}."
    return
  fi

  SERVICE_ARN=$(get_arn)
  TASK_DEF=$(get_task_def)
  aws ecs update-service \
    --cluster ${CLUSTER_NAME} \
    --service ${SERVICE_ARN} \
    --task-definition ${TASK_DEF} \
    --enable-execute-command \
    --force-new-deployment \
    --profile default
}

login() {
  _valify_cluster_name
  _valify_service_name

  # First check if execute command is enabled
  ENABLED=$(is_execute_command_enabled)
  if [ "${ENABLED}" == "false" ]; then
    echo "Execute command is not enabled for ${SERVICE_NAME}."
    echo "Run 'enable_execute_command' first to enable it."
    return
  fi

  # Get task and container details
  CONTAINER_ARN=$(get_conatiner_arn)
  TASK_ARN=$(get_task_arn)

  # Check if task is running
  TASK_STATUS=$(aws ecs describe-tasks \
    --cluster=${CLUSTER_NAME} \
    --tasks=${TASK_ARN} \
    --profile default | jq '.tasks[0].lastStatus' --raw-output)

  if [ "${TASK_STATUS}" != "RUNNING" ]; then
    echo "Task is not in RUNNING state (current status: ${TASK_STATUS}). Cannot connect."
    return
  fi

  echo "Logging into ${SERVICE_NAME}@${CONTAINER_ARN}..."
  echo ">> Task ARN: ${TASK_ARN}"
  echo ">> Container ARN: ${CONTAINER_ARN}"

  # Execute command with error handling
  aws ecs execute-command \
    --cluster=${CLUSTER_NAME} \
    --task=${TASK_ARN} \
    --container=${CONTAINER_ARN} \
    --command="/bin/${SHELL_TYPE}" \
    --interactive \
    --profile default

  if [ $? -ne 0 ]; then
    echo ""
    echo "Failed to connect. Possible reasons:"
    echo "1. SSM agent might not be running in the container"
    echo "2. Task might not have proper IAM permissions for SSM"
    echo "3. Network connectivity issues"
    echo "4. Container might not have the specified shell (${SHELL_TYPE})"
    echo ""
    echo "Check the task's IAM role and ensure it has the following policies:"
    echo "  - AmazonEC2ContainerServiceforEC2Role"
    echo "  - AmazonSSMManagedInstanceCore"
  fi
}

help() {
  echo "Usage: aws-ecs-service.sh [OPTIONS] [ARGUMENTS]"
  echo "  -h, --help        Show this help message and exit."
  echo "  -f, --func        Specify the function to run."
  echo "                    Available functions: "
  echo "                      - get_arn"
  echo "                      - get_conatiner_arn"
  echo "                      - get_task_arn"
  echo "                      - get_task_def"
  echo "                      - is_execute_command_enabled"
  echo "                      - enable_execute_command"
  echo "                      - login"
  echo "  -c, --cluster     Specify the ECS cluster name (default: green-detective)."
  echo "  -s, --service     Specify the ECS service name."
  echo "      --shell-type  Shell type to login to the container (default: bash)."
  echo ""
}

_check_libs
_handle_opts "$@"
_process_cmd
