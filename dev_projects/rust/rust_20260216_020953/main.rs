use std::error::Error;
use reqwest::{Client, Error as ReqwestError};
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_jira_issue(issue_key: &str) -> Result<JiraIssue, Box<dyn Error>> {
    let client = Client::new();
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = client.get(url).send().await?;

    if !response.status().is_success() {
        return Err(format!("Failed to fetch JIRA issue: {}", response.text().await?).into());
    }

    let json_value: Value = serde_json::from_str(&response.text().await?)?;
    let issue_data = json_value["fields"].as_object()?;

    Ok(JiraIssue {
        key: issue_data["key"].as_str()?.to_string(),
        summary: issue_data["summary"].as_str()?.to_string(),
        status: issue_data["status"]["name"].as_str()?.to_string(),
    })
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let issue_key = "ABC-123";
    let jira_issue = fetch_jira_issue(issue_key).await?;

    println!("JIRA Issue: {:?}", jira_issue);

    Ok(())
}