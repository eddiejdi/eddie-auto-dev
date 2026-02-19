use crate::Issue;
use reqwest::{Error, Response};
use serde_json::Value;

#[tokio::test]
async fn test_get_issue_success() {
    let issue_key = "RUST-12";
    let response = reqwest::get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key)).await;
    assert!(response.is_ok());
    let issue: Issue = response.json().await.unwrap();
    assert_eq!(issue.key, "RUST-12");
}

#[tokio::test]
async fn test_get_issue_error() {
    let response = reqwest::get("https://your-jira-instance.atlassian.net/rest/api/2/issue/nonexistent").await;
    assert!(!response.is_ok());
}

#[tokio::test]
async fn test_monitor_issue_success() {
    let issue_key = "RUST-12";
    let mut last_status = String::new();
    loop {
        let issue = get_issue(issue_key).await.unwrap();
        if issue.status != last_status {
            println!("Issue {} has changed status to {}", issue.key, issue.status);
            last_status = issue.status.clone();
        }
        tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
    }
}

#[tokio::test]
async fn test_monitor_issue_error() {
    let response = reqwest::get("https://your-jira-instance.atlassian.net/rest/api/2/issue/nonexistent").await;
    assert!(!response.is_ok());
}