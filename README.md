# 🥗 Smart Daily Meal Planner Assistant

A fully serverless AI-powered meal planning web app, built on AWS.  
Migrated from a PartyRock prototype to production-grade infrastructure.

---

## Architecture

```
Browser (S3 Static Website)
  │
  ├── POST  →  MealPlanFunction URL          (streaming Flask Lambda)
  │              └── Bedrock → Claude Haiku 4.5 (global cross-region)
  │
  └── POST  →  MealPlanningChatFunction URL  (streaming Flask Lambda)
                 └── Bedrock → Claude Haiku 4.5 (global cross-region)
```

| Layer        | Service                              |
|--------------|--------------------------------------|
| Frontend     | Amazon S3 Static Website Hosting     |
| Backend      | AWS Lambda (Python 3.12, Flask)      |
| AI Model     | Amazon Bedrock — Claude Haiku 4.5    |
| Streaming    | Lambda Function URLs (RESPONSE_STREAM) |
| IaC          | AWS SAM                              |
| CI/CD        | GitHub Actions                       |

---

## Project Structure

```
smart-daily-meal-planner/
├── backend/
│   ├── meal_plan/
│   │   ├── app.py            # Flask streaming Lambda — meal plan generation
│   │   ├── requirements.txt
│   │   └── run.sh            # Lambda Web Adapter entrypoint
│   └── meal_planning_chat/
│       ├── app.py            # Flask streaming Lambda — chat assistant
│       ├── requirements.txt
│       └── run.sh
├── frontend/
│   └── index.html            # Single-page app (S3 hosted)
├── infra/
│   └── template.yaml         # AWS SAM template
├── .github/
│   └── workflows/
│       └── deploy.yml        # CI/CD pipeline
└── README.md
```

---

## Pre-Deployment Checklist

### 1. Enable Bedrock Model Access

Go to **AWS Console → Amazon Bedrock → Model Access** in `ap-southeast-1`:

- Enable: **Claude Haiku 4.5** (`global.anthropic.claude-haiku-4-5-20251001-v1:0-20260217-v1:0`)

> First-time accounts may need to submit a brief use-case form.  
> The `global.` inference profile routes traffic worldwide for maximum throughput.

### 2. Create an S3 bucket for SAM deployment artifacts

```bash
aws s3 mb s3://YOUR-SAM-DEPLOY-BUCKET --region ap-southeast-1
```

This is separate from the frontend bucket (SAM creates the frontend bucket automatically).

### 3. Create an IAM user for GitHub Actions (least-privilege)

The deploying IAM user/role needs these permissions:

- `cloudformation:*` (or scoped to the stack)
- `s3:*` on the SAM deploy bucket and frontend bucket
- `lambda:*`
- `iam:*` (for creating the Lambda execution role)
- `bedrock:ListFoundationModels` (optional, for validation)

> **Recommendation:** Create a dedicated `github-actions-deployer` IAM user with a  
> scoped permissions boundary. Never use root credentials.

---

## GitHub Actions Setup

Add these **repository secrets** in GitHub → Settings → Secrets → Actions:

| Secret                  | Value                                          |
|-------------------------|------------------------------------------------|
| `AWS_ACCESS_KEY_ID`     | Access key ID for your deployer IAM user       |
| `AWS_SECRET_ACCESS_KEY` | Secret access key for your deployer IAM user   |
| `SAM_DEPLOY_BUCKET`     | Name of your SAM artifact S3 bucket            |

---

## Deploying

Push to `main` — the workflow runs automatically:

```bash
git add .
git commit -m "Initial deployment"
git push origin main
```

Or trigger manually: **GitHub → Actions → Deploy Smart Daily Meal Planner → Run workflow**

The workflow will:
1. Build Lambda packages with SAM
2. Deploy the CloudFormation stack
3. Read the Lambda Function URLs from stack outputs
4. Inject the URLs into `frontend/index.html`
5. Sync the frontend to S3
6. Print the live website URL in the workflow log

---

## Local Development

### Run a Lambda locally (no Docker required)

```bash
cd backend/meal_plan
pip install -r requirements.txt
python app.py
# Flask starts on http://localhost:8080
```

Test with curl:

```bash
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{"dietary_preference":"Vegan","num_days":3}'
```

### Chat Lambda

```bash
cd backend/meal_planning_chat
pip install -r requirements.txt
python app.py

curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{"message":"Give me a grocery list","history":[],"meal_plan_context":""}'
```

---

## API Reference

### POST `/` — Meal Plan Lambda

**Request body:**
```json
{
  "dietary_preference": "Vegan",
  "num_days": 5,
  "file_data": "<optional base64 string>",
  "file_mime": "<optional MIME type e.g. image/jpeg>"
}
```

**Response:** `text/plain` stream of the generated meal plan (token-by-token).

---

### POST `/` — Chat Lambda

**Request body:**
```json
{
  "message": "Can you give me a grocery list?",
  "history": [
    { "role": "user",      "content": "What can I substitute for chicken?" },
    { "role": "assistant", "content": "You could use tofu or tempeh..." }
  ],
  "meal_plan_context": "<optional: current meal plan text for context>"
}
```

**Response:** `text/plain` stream of the assistant reply (token-by-token).

---

## Cleanup

To delete all AWS resources:

```bash
# Delete the CloudFormation stack (removes Lambdas, IAM role)
aws cloudformation delete-stack \
  --stack-name smart-daily-meal-planner-assistant \
  --region ap-southeast-1

# Empty and delete the frontend bucket (substitute real bucket name)
aws s3 rm s3://smart-meal-planner-frontend-<ACCOUNT_ID> --recursive
aws s3 rb s3://smart-meal-planner-frontend-<ACCOUNT_ID>
```

---

## Model & Cost Notes

- **Model:** `global.anthropic.claude-haiku-4-5-20251001-v1:0-20260217-v1:0`  
  Claude Haiku 4.5 via the global cross-region inference profile.
- **Pricing:** Charged per input/output token. Haiku is the most cost-effective Claude model.
- **`max_tokens`:** Set to `2048` (meal plan) and `1024` (chat) — always explicit to avoid quota over-reservation.
- **Lambda:** Pay-per-invocation with 256 MB memory and 60 s timeout. Well within free tier for low traffic.
# Smart-Daily-Meal-Planner
