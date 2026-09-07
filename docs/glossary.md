# Terms used in the labs

| Term | Meaning here |
| --- | --- |
| Feature / label | Flower measurement / species to predict |
| Training / validation / test | Learn parameters / choose releases / final independent report |
| Pipeline | Fitted scaler and classifier kept together |
| Run | One training attempt and its recorded evidence |
| Artifact | A saved file, such as the fitted model or metrics |
| Lineage | Which code, data and dependencies produced a model |
| Gate | Rules that a candidate must pass before approval |
| Incumbent | Current approved model used as the regression comparison |
| Registry | Version records, approval decisions and history |
| Release bundle | Approved model and metadata packaged for deployment |
| Image / digest | Container runtime / content identifier fixing its exact bytes |
| Endpoint | Managed service address receiving prediction requests |
| Deployment / endpoint config | Azure running model allocation / AWS configuration selecting the hosted model |
| Staging | A candidate instance tested before changing production routing |
| Promotion | An explicit approval or routing change; the lesson states which |
| Smoke test | A small request checking the response and served model version |
| Rollback | Restore a previously approved, retained release |
| Drift | A change in observed input distribution; not proof of lost accuracy |
| Ground truth / feedback | Independently obtained labels joined to previous predictions |
| IAM / RBAC | Permissions deciding which identity may perform an action |
| Quota | Your account's allowed allocation, separate from regional capacity |
| CI / continuous delivery | Automated code checks / repeatable release steps with approval |

Return to the [course guide](00-course-guide.md).
