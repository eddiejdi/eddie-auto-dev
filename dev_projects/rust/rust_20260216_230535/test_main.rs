use serde_json;
use reqwest;

#[tokio::test]
async fn test_create_issue_success() {
    let base_url = "https://your-jira-instance.atlassian.net";
    let auth_token = "your-auth-token";
    let client = JiraClient::new(base_url, auth_token);

    let cli = JiraCli::new(client);
    let issue = JiraIssue::new("JIRA-123", "Fix bug in login page", "In Progress");

    assert!(cli.create_issue(&issue).await.is_ok());
}

#[tokio::test]
async fn test_create_issue_failure() {
    let base_url = "https://your-jira-instance.atlassian.net";
    let auth_token = "your-auth-token";
    let client = JiraClient::new(base_url, auth_token);

    let cli = JiraCli::new(client);
    let issue = JiraIssue::new("JIRA-123", "Fix bug in login page", "In Progress");

    assert!(cli.create_issue(&issue).await.is_err());
}