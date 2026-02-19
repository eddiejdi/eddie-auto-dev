use reqwest;
use serde_json::Value;

#[tokio::test]
async fn create_issue_success() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-auth-token");

    let issue_data = json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Rust Agent Integration",
            "description": "This is a test for the Rust Agent integration with Jira.",
            "issuetype": {"name": "Bug"}
        }
    });

    let issue_response = jira_client.create_issue(issue_data).await.unwrap();

    assert_eq!(issue_response["key"], "YOUR_PROJECT_KEY-12345");
}

#[tokio::test]
async fn create_issue_failure() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-auth-token");

    let issue_data = json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Rust Agent Integration",
            "description": "This is a test for the Rust Agent integration with Jira.",
            "issuetype": {"name": "Bug"}
        }
    });

    let issue_response = jira_client.create_issue(issue_data).await.unwrap_err();

    assert_eq!(issue_response.status(), reqwest::StatusCode::INTERNAL_SERVER_ERROR);
}