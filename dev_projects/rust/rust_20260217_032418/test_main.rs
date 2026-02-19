use reqwest;
use serde_json;

#[tokio::test]
async fn create_issue_success() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net/rest/api/2/", "your-auth-token");
    let response = jira_client.create_issue("YOUR-PROJECT", "Bug in Rust Agent", "This is a test bug for the Rust Agent.").await;
    assert!(response.is_ok());
}

#[tokio::test]
async fn create_issue_failure() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net/rest/api/2/", "your-auth-token");
    let response = jira_client.create_issue("YOUR-PROJECT", "", "").await;
    assert!(response.is_err());
}

#[tokio::test]
async fn get_issues_success() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net/rest/api/2/", "your-auth-token");
    let response = jira_client.get_issues().await;
    assert!(response.is_ok());
}

#[tokio::test]
async fn get_issues_failure() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net/rest/api/2/", "your-auth-token");
    let response = jira_client.get_issues().await;
    assert!(response.is_err());
}