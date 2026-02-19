use reqwest;
use serde_json::Value;

#[tokio::test]
async fn create_issue_success() {
    let token = "your-jira-token";
    let client = JiraClient::new(token);

    let issue = Issue::new("TEST-123", "Test issue summary", "Open");

    assert!(client.create_issue(issue).await.is_ok());
}

#[tokio::test]
async fn create_issue_error() {
    let token = "your-jira-token";
    let client = JiraClient::new(token);

    // Test case for invalid token
    let issue = Issue::new("TEST-123", "Test issue summary", "Open");
    assert!(client.create_issue(issue).await.is_err());

    // Test case for missing fields
    let issue = Issue::new("", "", "");
    assert!(client.create_issue(issue).await.is_err());
}