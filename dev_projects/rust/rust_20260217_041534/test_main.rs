use reqwest;
use serde_json::Value;

#[tokio::test]
async fn create_issue_success() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-api-token");
    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent.",
            "issuetype": {"name": "Bug"}
        }
    });

    let response = jira_client.create_issue(issue_data).await.unwrap();

    assert_eq!(response, "issue created successfully");
}

#[tokio::test]
async fn create_issue_error() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-api-token");

    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "",
            "description": "",
            "issuetype": {"name": ""}
        }
    });

    let response = jira_client.create_issue(issue_data).await.unwrap_err();

    assert_eq!(response.status(), reqwest::StatusCode::BAD_REQUEST);
}