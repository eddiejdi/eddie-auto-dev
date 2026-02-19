use reqwest::Error;
use serde_json::{Value, from_str};
use std::env;

#[tokio::test]
async fn test_new() {
    let url = "https://your-jira-instance.atlassian.net";
    let token = "your-api-token";

    Jira::new(url, token);
}

#[tokio::test]
async fn test_get_issues_success() -> Result<(), Error> {
    let jira = Jira::new("https://your-jira-instance.atlassian.net", "your-api-token");
    // Simulate a successful response
    let body = r#"[{"key": "ABC123"}, {"key": "XYZ456"}]"#;
    let response = reqwest::Response::builder()
        .status(200)
        .body(body.to_string())
        .build()?;

    let issues = jira.get_issues().await?;
    assert_eq!(issues.len(), 2);
    Ok(())
}

#[tokio::test]
async fn test_get_issues_error() {
    let jira = Jira::new("https://your-jira-instance.atlassian.net", "your-api-token");
    // Simulate an error response
    let response = reqwest::Response::builder()
        .status(500)
        .body(r#"{"error": "Internal Server Error"}"#.to_string())
        .build()?;

    assert_eq!(jira.get_issues().await, Err(reqwest::Error::from(response.status())));
}

#[tokio::test]
async fn test_create_issue_success() {
    let jira = Jira::new("https://your-jira-instance.atlassian.net", "your-api-token");
    // Simulate a successful response
    let body = r#"{"key": "XYZ789"}"#;
    let response = reqwest::Response::builder()
        .status(201)
        .body(body.to_string())
        .build()?;

    assert_eq!(jira.create_issue(&json!({"fields": {"project": {"key": "YOUR-PROJECT"}, "summary": "Test issue", "description": "This is a test issue created by Rust Agent.", "issuetype": {"name": "Bug"}}})).await, Ok(()));
}

#[tokio::test]
async fn test_create_issue_error() {
    let jira = Jira::new("https://your-jira-instance.atlassian.net", "your-api-token");
    // Simulate an error response
    let response = reqwest::Response::builder()
        .status(400)
        .body(r#"{"error": "Invalid JSON"}"#.to_string())
        .build()?;

    assert_eq!(jira.create_issue(&json!({"fields": {"project": {"key": "YOUR-PROJECT"}, "summary": "Test issue", "description": "This is a test issue created by Rust Agent.", "issuetype": {"name": "Bug"}}})).await, Err(reqwest::Error::from(response.status())));
}