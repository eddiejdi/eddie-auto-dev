use crate::fetch_jira_issue;
use crate::update_jira_issue;
use reqwest::{Error, Response};
use serde_json::{from_str, Value};

#[tokio::test]
async fn test_fetch_jira_issue_success() {
    let issue_key = "JIRA-123";
    let response = fetch_jira_issue(issue_key).await.unwrap();
    assert_eq!(response.key, "JIRA-123");
    assert_eq!(response.summary, "Test Issue");
    assert_eq!(response.status, "OPEN");
}

#[tokio::test]
async fn test_fetch_jira_issue_failure() {
    let issue_key = "INVALID-ISSUE";
    let result = fetch_jira_issue(issue_key).await;
    assert!(result.is_err());
}

#[tokio::test]
async fn test_update_jira_issue_success() {
    let issue_key = "JIRA-123";
    update_jira_issue(issue_key, "IN_PROGRESS").await.unwrap();
}

#[tokio::test]
async fn test_update_jira_issue_failure() {
    let issue_key = "INVALID-ISSUE";
    let result = update_jira_issue(issue_key, "UNKNOWN");
    assert!(result.is_err());
}