param(
    [Parameter(Mandatory=$true)][string]$ApprovalFile,
    [Parameter(Mandatory=$true)][string]$ServiceAccount,
    [Parameter(Mandatory=$true)][string]$YoutubeSecret,
    [Parameter(Mandatory=$true)][string]$ApprovalSecret,
    [switch]$EnableSchedule
)
$ErrorActionPreference = 'Stop'
$env:CLOUDSDK_CORE_DISABLE_PROMPTS = '1'
$taskRoot = Split-Path -Parent $PSScriptRoot
$approval = Get-Content -Raw -Encoding UTF8 -LiteralPath $ApprovalFile | ConvertFrom-Json
if (-not $approval.explicit_user_approval -or $approval.total_cap_jpy -le 0) { throw 'Explicit cost approval is required.' }
if ($approval.dataset -ne 'zunda_all' -or $approval.project -ne 'rugged-destiny-408613') { throw 'Approval target mismatch.' }
if ($approval.valid_until -lt (Get-Date -Format 'yyyy-MM-dd')) { throw 'Approval expired.' }
$account = & gcloud auth list --filter='status:ACTIVE' --format='value(account)'
if ($account -ne 'japonismy@gmail.com') { throw 'The required GCP account is not active.' }
$projectId = 'rugged-destiny-408613'
$region = 'asia-northeast1'
$jobName = 'zunda-daily-metadata'
$image = "$region-docker.pkg.dev/$projectId/cloud-run-source-deploy/${jobName}:v1"
Set-Location -LiteralPath $taskRoot
# Build has a hard timeout. No automatic retry and no source from private data.
& gcloud builds submit --project=$projectId --region=$region --config=backend/cloudbuild.yaml --timeout=1200s .
if ($LASTEXITCODE -ne 0) { throw 'Cloud build failed. No retry.' }
& gcloud run jobs deploy $jobName --project=$projectId --region=$region --image=$image --service-account=$ServiceAccount --tasks=1 --parallelism=1 --max-retries=0 --task-timeout=600s --cpu=1 --memory=512Mi --set-secrets="YOUTUBE_API_KEY=${YoutubeSecret}:latest,ZUNDA_COST_APPROVAL_JSON=${ApprovalSecret}:latest"
if ($LASTEXITCODE -ne 0) { throw 'Cloud Run deployment failed. No retry.' }
# Create paused. Activation is the final, separately selected step.
& gcloud scheduler jobs create http zunda-daily-metadata-schedule --project=$projectId --location=$region --schedule='20 3 * * *' --time-zone='Asia/Tokyo' --uri="https://run.googleapis.com/v2/projects/$projectId/locations/$region/jobs/${jobName}:run" --http-method=POST --oauth-service-account-email=$ServiceAccount
if ($LASTEXITCODE -ne 0) { throw 'Scheduler creation failed. Inspect existing state before retry.' }
& gcloud scheduler jobs pause zunda-daily-metadata-schedule --project=$projectId --location=$region
if ($LASTEXITCODE -ne 0) { throw 'Could not pause the new schedule.' }
if ($EnableSchedule) {
    if ('cloud_scheduler' -notin $approval.scopes) { throw 'Schedule activation is outside approval.' }
    & gcloud scheduler jobs resume zunda-daily-metadata-schedule --project=$projectId --location=$region
    if ($LASTEXITCODE -ne 0) { throw 'Scheduler activation failed.' }
}
