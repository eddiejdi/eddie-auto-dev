use crate::JiraClient;
use reqwest::{self, Error};
use serde_json::{self, Value};

#[tokio::test]
async fn test_jira_client_new() {
    let token = "YOUR_JIRA_TOKEN";
    let base_url = "https://your-jira-instance.atlassian.net";

    let client = JiraClient::new(token, base_url);
    assert_eq!(client.token, token.to_string());
    assert_eq!(client.base_url, base_url.to_string());
}

#[tokio::test]
async fn test_jira_client_get_issue_success() {
    let token = "YOUR_JIRA_TOKEN";
    let base_url = "https://your-jira-instance.atlassian.net";
    let issue_key = "ABC-123";

    let client = JiraClient::new(token, base_url);
    let response = client.get_issue(issue_key).await;
    assert!(response.is_ok());
}

#[tokio::test]
async fn test_jira_client_get_issue_error() {
    let token = "YOUR_JIRA_TOKEN";
    let base_url = "https://your-jira-instance.atlassian.net";

    let client = JiraClient::new(token, base_url);
    let response = client.get_issue("INVALID-KEY").await;
    assert!(response.is_err());
}

#[tokio::test]
async fn test_cli_app_run_success() {
    let token = "YOUR_JIRA_TOKEN";
    let base_url = "https://your-jira-instance.atlassian.net";

    let app = CliApp::new(token, base_url);
    let response = app.run().await;
    assert!(response.is_ok());
}

#[tokio::test]
async fn test_cli_app_run_error() {
    let token = "YOUR_JIRA_TOKEN";
    let base_url = "https://your-jira-instance.atlassian.net";

    let app = CliApp::new(token, base_url);
    let response = app.run().await;
    assert!(response.is_err());
}