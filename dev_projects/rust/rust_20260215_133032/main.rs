use reqwest;
use serde_json;

#[derive(Debug, Serialize)]
struct JiraIssue {
    key: String,
    summary: String,
    description: String,
}

async fn create_jira_issue(jira_url: &str, issue: JiraIssue) -> Result<(), Box<dyn std::error::Error>> {
    let response = reqwest::post(format!("{}rest/api/2/issue", jira_url))
        .json(&issue)
        .send()?;

    if response.status().is_success() {
        Ok(())
    } else {
        Err(response.text().await.map_err(|_| Box<dyn std::error::Error>::from("Failed to create JIRA issue"))?)
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net";
    let username = "your-username";
    let password = "your-password";

    let issue = JiraIssue {
        key: "ABC123".to_string(),
        summary: "Test Issue".to_string(),
        description: "This is a test issue created by Rust Agent.".to_string(),
    };

    create_jira_issue(jira_url, issue).await?;

    println!("JIRA issue created successfully.");

    Ok(())
}