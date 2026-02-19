use reqwest;
use serde_json::{self, Value};
use tokio::sync::mpsc;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_jira_issue(issue_key: &str) -> Result<JiraIssue, Box<dyn std::error::Error>> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    if response.status().is_success() {
        let json: Value = serde_json::from_str(&response.text().await)?;
        Ok(JiraIssue {
            key: json["key"].as_str().unwrap().to_string(),
            summary: json["fields"]["summary"].as_str().unwrap().to_string(),
            status: json["fields"]["status"]["name"].as_str().unwrap().to_string(),
        })
    } else {
        Err(Box::new(response.text().await.unwrap().into()))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut issues = Vec::new();
    for issue_key in ["ABC-123", "XYZ-456"] {
        let issue = fetch_jira_issue(issue_key).await?;
        issues.push(issue);
    }

    // Simulate processing of issues
    for issue in &issues {
        println!("Issue: {}", issue.key);
        println!("Summary: {}", issue.summary);
        println!("Status: {}", issue.status);
        println!();
    }

    Ok(())
}

#[tokio::test]
async fn test_fetch_jira_issue_success() {
    let response = reqwest::get("https://your-jira-instance.atlassian.net/rest/api/2/issue/ABC-123").await.unwrap();
    assert_eq!(response.status(), reqwest::StatusCode::OK);

    let json: Value = serde_json::from_str(&response.text().await.unwrap()).unwrap();
    assert_eq!(json["key"].as_str().unwrap(), "ABC-123");
    assert_eq!(json["fields"]["summary"].as_str().unwrap(), "Test Issue");
    assert_eq!(json["fields"]["status"]["name"].as_str().unwrap(), "To Do");
}

#[tokio::test]
async fn test_fetch_jira_issue_failure() {
    let response = reqwest::get("https://your-jira-instance.atlassian.net/rest/api/2/issue/ABC-123").await.unwrap();
    assert_eq!(response.status(), reqwest::StatusCode::NOT_FOUND);

    let json: Value = serde_json::from_str(&response.text().await.unwrap()).unwrap();
    assert_eq!(json["errorMessages"][0].as_str().unwrap(), "Resource not found");
}

#[tokio::test]
async fn test_fetch_jira_issue_error_handling() {
    let response = reqwest::get("https://your-jira-instance.atlassian.net/rest/api/2/issue/ABC-123").await.unwrap();
    assert_eq!(response.status(), reqwest::StatusCode::INTERNAL_SERVER_ERROR);

    let json: Value = serde_json::from_str(&response.text().await.unwrap()).unwrap();
    assert_eq!(json["errorMessages"][0].as_str().unwrap(), "Internal server error");
}