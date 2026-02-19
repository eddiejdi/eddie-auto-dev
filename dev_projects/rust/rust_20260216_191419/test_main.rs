use crate::create_issue;
use crate::get_issues;
use reqwest::{Error, Response};
use serde_json::Value;

#[tokio::test]
async fn create_issue_success() {
    let issue = Issue {
        key: "RUST-123".to_string(),
        summary: "Implement Rust Agent with Jira tracking",
        description: "This is a test issue for the Rust Agent with Jira integration.",
    };
    assert!(create_issue(&issue).await.is_ok());
}

#[tokio::test]
async fn create_issue_failure() {
    let issue = Issue {
        key: "RUST-123".to_string(),
        summary: "Implement Rust Agent with Jira tracking",
        description: "",
    };
    assert!(create_issue(&issue).await.is_err());
}

#[tokio::test]
async fn get_issues_success() {
    // This test assumes that the `get_issues` function returns a list of issues
    let issues = get_issues().await.unwrap();
    assert!(!issues.is_empty());
}

#[tokio::test]
async fn get_issues_failure() {
    // This test assumes that the `get_issues` function returns an error
    assert!(get_issues().await.is_err());
}