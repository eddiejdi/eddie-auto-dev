use reqwest;
use serde_json::{Value, Result};
use chrono::prelude::*;

mod jira_client {
    use super::*;

    #[tokio::test]
    async fn get_issues_success() {
        let client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-auth-token");
        let query = "project=YOUR_PROJECT AND status IN (OPEN, IN_PROGRESS)";
        let issues = client.get_issues(query).await.unwrap();
        assert!(!issues.is_empty());
    }

    #[tokio::test]
    async fn get_issues_error() {
        let client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-auth-token");
        let query = "project=YOUR_PROJECT AND status IN (INVALID)";
        match client.get_issues(query).await {
            Ok(_) => panic!("Expected an error"),
            Err(e) => assert_eq!(e.status(), reqwest::StatusCode::NOT_FOUND),
        }
    }

    #[tokio::test]
    async fn create_issue_success() {
        let client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-auth-token");
        let issue_data = serde_json::json!({
            "fields": {
                "project": {"key": "YOUR_PROJECT"},
                "summary": "Example Issue",
                "description": "This is an example issue created via Rust.",
                "issuetype": {"name": "Bug"}
            }
        });
        let new_issue = client.create_issue(&issue_data).await.unwrap();
        assert!(!new_issue.is_empty());
    }

    #[tokio::test]
    async fn create_issue_error() {
        let client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-auth-token");
        let issue_data = serde_json::json!({
            "fields": {
                "project": {"key": "INVALID_PROJECT"},
                "summary": "Example Issue",
                "description": "This is an example issue created via Rust.",
                "issuetype": {"name": "Bug"}
            }
        });
        match client.create_issue(&issue_data).await {
            Ok(_) => panic!("Expected an error"),
            Err(e) => assert_eq!(e.status(), reqwest::StatusCode::NOT_FOUND),
        }
    }
}