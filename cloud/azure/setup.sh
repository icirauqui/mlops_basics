#!/usr/bin/env bash
# Run from the repository root after reviewing docs/07-azure-setup.md.
set -euo pipefail
: "${AZURE_SUBSCRIPTION_ID:?Set the subscription ID}"
: "${AZURE_RESOURCE_GROUP:?Set a dedicated course resource group}"
: "${AZURE_ML_WORKSPACE:?Set the workspace name}"
: "${AZURE_LOCATION:?Set a region with CPU quota}"
: "${AZURE_ACR_NAME:?Set a globally unique alphanumeric registry name}"

az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az extension add --name ml --upgrade --yes
az group create --name "$AZURE_RESOURCE_GROUP" --location "$AZURE_LOCATION"
az acr create --name "$AZURE_ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --sku Basic
course_acr_id=$(az acr show --name "$AZURE_ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query id -o tsv)
az ml workspace create --name "$AZURE_ML_WORKSPACE" --resource-group "$AZURE_RESOURCE_GROUP" \
  --location "$AZURE_LOCATION" --container-registry "$course_acr_id"
az ml compute create --file cloud/azure/compute.yml --workspace-name "$AZURE_ML_WORKSPACE" \
  --resource-group "$AZURE_RESOURCE_GROUP"
