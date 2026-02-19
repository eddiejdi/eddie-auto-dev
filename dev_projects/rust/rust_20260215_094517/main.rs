use reqwest;
use serde_json;

#[derive(serde::Deserialize)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn get_jira_issue(issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    response.json().await
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let issue_key = "JIRA-123";
    let jira_issue = get_jira_issue(issue_key).await?;

    println!("Issue Key: {}", jira_issue.key);
    println!("Summary: {}", jira_issue.summary);
    println!("Status: {}", jira_issue.status);

    Ok(())
}