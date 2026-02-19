use reqwest::Error;
use serde_json::{from_str, Value};

#[tokio::test]
async fn test_get_issue_success() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net");
    let issue_key = "ABC-123";
    let response = jira_client.get_issue(issue_key).await;

    assert!(response.is_ok());
    match response {
        Ok(issue) => {
            assert_eq!(issue.key, "ABC-123");
            assert_eq!(issue.summary, "Sample Issue");
            assert_eq!(issue.status, "Open");
        }
        Err(e) => panic!("Error fetching issue: {}", e),
    }
}

#[tokio::test]
async fn test_get_issue_failure() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net");
    let response = jira_client.get_issue("INVALID-KEY").await;

    assert!(response.is_err());
}

#[tokio::test]
async fn test_update_issue_status_success() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net");
    let issue_key = "ABC-123";
    let new_status = "In Progress";

    let response = jira_client.update_issue_status(issue_key, &new_status).await;

    assert!(response.is_ok());
}

#[tokio::test]
async fn test_update_issue_status_failure() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net");
    let issue_key = "INVALID-KEY";
    let new_status = "In Progress";

    let response = jira_client.update_issue_status(issue_key, &new_status).await;

    assert!(response.is_err());
}