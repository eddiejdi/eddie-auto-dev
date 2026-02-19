use crate::Issue;
use crate::JiraResponse;
use reqwest::{Error, Response};
use serde_json::Value;

// Test function for create_issue
#[tokio::test]
async fn test_create_issue() {
    let jira_url = "https://your-jira-instance.atlassian.net";
    let username = "your-username";
    let password = "your-password";
    let summary = "Task 1";
    let description = "This is a test task.";

    // Mock response for success
    let mock_response = Response::builder()
        .status(201)
        .header("Content-Type", "application/json")
        .body(r#"{"issues":[{"key":"ABC-123","summary":"Task 1","description":"This is a test task."}]}"#)
        .unwrap();

    // Mock client to return the mock response
    let mock_client = reqwest::Client::builder()
        .base_url(jira_url)
        .build()
        .unwrap();

    // Call create_issue with mock client and expected data
    let result = create_issue(&mock_client, username, password, summary, description).await;

    // Assert that the result is Ok and contains the expected issue
    assert!(result.is_ok());
    let issues = result.unwrap();
    assert_eq!(issues.len(), 1);
    assert_eq!(issues[0].key, "ABC-123");
    assert_eq!(issues[0].summary, "Task 1");
    assert_eq!(issues[0].description, "This is a test task.");
}

// Test function for list_issues
#[tokio::test]
async fn test_list_issues() {
    let jira_url = "https://your-jira-instance.atlassian.net";
    let username = "your-username";
    let password = "your-password";

    // Mock response for success
    let mock_response = Response::builder()
        .status(200)
        .header("Content-Type", "application/json")
        .body(r#"{"issues":[{"key":"ABC-123","summary":"Task 1","description":"This is a test task."}]}"#)
        .unwrap();

    // Mock client to return the mock response
    let mock_client = reqwest::Client::builder()
        .base_url(jira_url)
        .build()
        .unwrap();

    // Call list_issues with mock client and expected data
    let result = list_issues(&mock_client, username, password).await;

    // Assert that the result is Ok and contains the expected issues
    assert!(result.is_ok());
    let issues = result.unwrap();
    assert_eq!(issues.len(), 1);
    assert_eq!(issues[0].key, "ABC-123");
    assert_eq!(issues[0].summary, "Task 1");
    assert_eq!(issues[0].description, "This is a test task.");
}