use crate::JiraClient;
use serde_json::{Value};
use reqwest::Error;

#[tokio::test]
async fn test_create_issue() {
    let client = JiraClient::new("your_token");
    let issue = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent."
        }
    });

    match client.create_issue(&issue).await {
        Ok(_) => println!("Issue created successfully."),
        Err(e) => panic!("Failed to create issue: {}", e),
    }
}

#[tokio::test]
async fn test_update_issue() {
    let client = JiraClient::new("your_token");
    let issue_key = "YOUR_ISSUE_KEY";
    let issue = serde_json::json!({
        "fields": {
            "summary": "Updated Issue",
            "description": "This is an updated issue created by Rust Agent."
        }
    });

    match client.update_issue(issue_key, &issue).await {
        Ok(_) => println!("Issue updated successfully."),
        Err(e) => panic!("Failed to update issue: {}", e),
    }
}

#[tokio::test]
async fn test_delete_issue() {
    let client = JiraClient::new("your_token");
    let issue_key = "YOUR_ISSUE_KEY";

    match client.delete_issue(issue_key).await {
        Ok(_) => println!("Issue deleted successfully."),
        Err(e) => panic!("Failed to delete issue: {}", e),
    }
}

#[tokio::test]
async fn test_get_issue() {
    let client = JiraClient::new("your_token");
    let issue_key = "YOUR_ISSUE_KEY";

    match client.get_issue(issue_key).await {
        Ok(issue) => println!("{:?}", issue),
        Err(e) => panic!("Failed to retrieve issue: {}", e),
    }
}