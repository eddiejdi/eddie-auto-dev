use reqwest;
use serde_json::Value;
use std::env;

mod jira_client {
    use super::*;

    #[tokio::test]
    async fn create_issue_success() {
        let jira_base_url = env::var("JIRA_BASE_URL").unwrap();
        let issue_data = serde_json::json!({
            "fields": {
                "project": {"key": "YOUR_PROJECT_KEY"},
                "summary": "Test Issue",
                "description": "This is a test issue created by Rust Agent",
                "issuetype": {"name": "Bug"}
            }
        });

        let client = JiraClient::new(&jira_base_url);
        let response = client.create_issue(issue_data).await.unwrap();

        assert_eq!(response, "{\"key\": \"YOUR_PROJECT_KEY-12345\"}");
    }

    #[tokio::test]
    async fn create_issue_error() {
        let jira_base_url = env::var("JIRA_BASE_URL").unwrap();
        let issue_data = serde_json::json!({
            "fields": {
                "project": {"key": "YOUR_PROJECT_KEY"},
                "summary": "Test Issue",
                "description": "This is a test issue created by Rust Agent",
                "issuetype": {"name": "Bug"}
            }
        });

        let client = JiraClient::new(&jira_base_url);
        let response = client.create_issue(issue_data).await.unwrap_err();

        assert_eq!(response.status(), reqwest::StatusCode::INTERNAL_SERVER_ERROR);
    }

    #[tokio::test]
    async fn create_issue_edge_case() {
        let jira_base_url = env::var("JIRA_BASE_URL").unwrap();
        let issue_data = serde_json::json!({
            "fields": {
                "project": {"key": "YOUR_PROJECT_KEY"},
                "summary": "",
                "description": "",
                "issuetype": {"name": "Bug"}
            }
        });

        let client = JiraClient::new(&jira_base_url);
        let response = client.create_issue(issue_data).await.unwrap_err();

        assert_eq!(response.status(), reqwest::StatusCode::BAD_REQUEST);
    }
}