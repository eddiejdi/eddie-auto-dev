use reqwest;
use serde_json;

#[tokio::test]
async fn create_issue_success() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "YOUR_AUTH_TOKEN");
    let issue_key = "ABC-123";
    let summary = "Bug in the login page";
    let description = "The user cannot log in to the application.";

    assert!(jira_client.create_issue(issue_key, summary, description).await.is_ok());
}

#[tokio::test]
async fn create_issue_error() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "YOUR_AUTH_TOKEN");
    let issue_key = "ABC-123";
    let summary = "Bug in the login page";
    let description = "The user cannot log in to the application.";

    assert!(jira_client.create_issue(issue_key, summary, description).await.is_err());
}