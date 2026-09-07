# Lesson 07: Prepare Azure Machine Learning

**Goal:** create a small, dedicated environment for custom model training and
hosting. Complete the local lessons and Docker smoke test first.

## Resources and access

Use an **Azure Machine Learning workspace**. A Microsoft Foundry project is not
needed for this classifier. The setup script creates a dedicated resource group,
a Basic Azure Container Registry (ACR), an Azure ML workspace and a CPU cluster.
Workspace creation provisions its supporting storage, Key Vault and monitoring
resources as required by the service. See the
[Azure ML workspace CLI](https://learn.microsoft.com/en-us/cli/azure/ml/workspace?view=azure-cli-latest).

The human running setup needs permission to create these resources, and may need
an administrator to register providers and assign roles. Workspace Contributor
permissions cover many control-plane operations, but data upload, image push
and inference can require additional data-plane roles. For a teaching account,
have the administrator check:

- Azure ML workspace/resource group access to submit jobs and create endpoints.
- Blob data access to the workspace storage for data and model uploads.
- `AcrPush` on the course registry for the image publisher.
- Managed identities can pull the image and read mounted model artifacts.
- The caller can invoke `aad_token` endpoints (`score/action` permission).

Do not solve a role error by placing account keys in a notebook. Keep human
login, compute identity and endpoint identity distinct. Review
[managed endpoint security](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-secure-online-endpoint?view=azureml-api-2)
when using organization-managed subscriptions.

## Sign in and create resources

Install the [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli),
then run these Bash commands from the repository root. Replace the values with
your subscription and unique names:

```bash
az login
export AZURE_SUBSCRIPTION_ID='your-subscription-uuid'
export AZURE_RESOURCE_GROUP='rg-iris-course'
export AZURE_ML_WORKSPACE='ml-iris-course'
export AZURE_LOCATION='westeurope'
export AZURE_ACR_NAME='youruniqueirisregistry'
bash cloud/azure/setup.sh
```

The registry name must be globally unique and alphanumeric. The region is an
example, not a capacity guarantee. Check quota for `Standard_DS3_v2` training
nodes and managed endpoint nodes before proceeding; use an available supported
CPU SKU if necessary. Edit `cloud/azure/compute.yml` for the cluster SKU and pass
`--instance-type` for deployment.

If providers are unregistered, an administrator can register
`Microsoft.MachineLearningServices`, `Microsoft.ContainerRegistry`,
`Microsoft.Storage`, `Microsoft.KeyVault`, and monitoring dependencies using
`az provider register --namespace NAME --wait`. Registration is subscription-wide.

The cluster uses minimum 0, maximum 1 node, and a 120-second idle scale-down
setting. Managed online deployments have their own always-running instances;
cluster scale-down does not stop endpoint charges.

## Push the tested image and resolve its digest

From the repository root after lesson 04's build:

```bash
az acr login --name "$AZURE_ACR_NAME"
export AZURE_ACR_SERVER=$(az acr show --name "$AZURE_ACR_NAME" --query loginServer -o tsv)
docker tag iris-course:v1 "$AZURE_ACR_SERVER/iris-course:v1"
docker push "$AZURE_ACR_SERVER/iris-course:v1"
export AZURE_IMAGE_DIGEST=$(az acr repository show --name "$AZURE_ACR_NAME" \
  --image iris-course:v1 --query digest -o tsv)
export AZURE_IMAGE="$AZURE_ACR_SERVER/iris-course@$AZURE_IMAGE_DIGEST"
cd python
uv sync --locked --extra azure
```

Keep the environment variables in your terminal. They contain identifiers, not
credentials. A `.env` file is ignored by Git but is not automatically loaded by
these scripts. `DefaultAzureCredential` can use your `az login` session locally.

For a code or dependency change, rebuild and push a new image tag, then use its
new digest. A model-only update may reuse the existing image if the inference
contract and dependency versions are unchanged.

## Cost and cleanup plan

Set a subscription/resource-group budget alert before the cloud lab. Consult
[Azure ML pricing](https://azure.microsoft.com/en-us/pricing/details/machine-learning/)
and [ACR pricing](https://azure.microsoft.com/en-us/pricing/details/container-registry/)
for your region and currency. No fixed price is assumed here. Online instances,
storage, registry and log ingestion can incur charges while idle; staging and
production deployments can temporarily double endpoint compute.

Use the group only for course resources. At the end of lesson 08, delete endpoints
and then the dedicated group. If you stop after setup, clean up now:

```bash
az group delete --name "$AZURE_RESOURCE_GROUP"
```

The CLI asks for deletion confirmation. Verify the selected group contains only
the lab, then wait for deletion and check Cost Management for residual resources
or delayed billing. Key Vault soft deletion can reserve names after cleanup.

**Done when:** the workspace and cluster exist, the image has a digest, and you
can explain which identity trains, pushes images and invokes the endpoint.

Next: [Azure lifecycle](08-azure-lifecycle.md).
