use reqwest;
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
}

async fn fetch_jira_issue(issue_key: &str) -> Result<JiraIssue, Box<dyn std::error::Error>> {
    let client = reqwest::Client::new();
    let response = client.get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key))
        .header("Authorization", "Basic your-base64-encoded-auth")
        .send()?;

    if !response.status().is_success() {
        return Err(format!("Failed to fetch issue: {}", response.status()).into());
    }

    let json = response.text()?;
    Ok serde_json::from_str(&json)?
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let issue_key = "ABC-123";
    let issue = fetch_jira_issue(issue_key).await?;

    println!("Issue Key: {}", issue.key);
    println!("Summary: {}", issue.summary);

    Ok(())
}