use reqwest;
use serde_json::Value;

#[tokio::test]
async fn create_issue_success() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-auth-token");

    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Test issue",
            "description": "This is a test issue created using Rust and Jira API",
            "issuetype": {"name": "Bug"}
        }
    });

    let response = jira_client.create_issue(issue_data).await.unwrap();

    assert_eq!(response["key"], "YOUR_PROJECT_KEY-12345"); // Example key
}

#[tokio::test]
async fn create_issue_failure() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-auth-token");

    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "",
            "description": "",
            "issuetype": {"name": "Bug"}
        }
    });

    match jira_client.create_issue(issue_data).await {
        Ok(_) => panic!("Expected an error but got a successful response"),
        Err(e) => assert_eq!(e.status(), reqwest::StatusCode::BAD_REQUEST),
    }
}