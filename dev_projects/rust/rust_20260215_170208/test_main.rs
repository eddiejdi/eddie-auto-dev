use crate::Issue;
use crate::AgentConfig;
use reqwest::{Error, Response};
use serde_json::Value;

#[tokio::test]
async fn test_fetch_issues_success() {
    let config = AgentConfig {
        token: "YOUR_JIRA_API_TOKEN",
        url: "https://your-jira-instance.atlassian.net/rest/api/2/",
    };

    let response = Response::builder()
        .status(200)
        .body("[]".to_string())
        .unwrap();

    let issues = fetch_issues(&config).await.unwrap();
    assert_eq!(issues.len(), 0);
}

#[tokio::test]
async fn test_fetch_issues_error() {
    let config = AgentConfig {
        token: "YOUR_JIRA_API_TOKEN",
        url: "https://your-jira-instance.atlassian.net/rest/api/2/",
    };

    let response = Response::builder()
        .status(401)
        .body("Unauthorized".to_string())
        .unwrap();

    let result = fetch_issues(&config).await;
    assert!(result.is_err());
}

#[tokio::test]
async fn test_create_task_success() {
    let config = AgentConfig {
        token: "YOUR_JIRA_API_TOKEN",
        url: "https://your-jira-instance.atlassian.net/rest/api/2/",
    };

    let issue_key = "ABC-123";
    let task_name = "New Task";

    let response = Response::builder()
        .status(201)
        .body("{}".to_string())
        .unwrap();

    create_task(&config, issue_key, task_name).await.unwrap();
}

#[tokio::test]
async fn test_create_task_error() {
    let config = AgentConfig {
        token: "YOUR_JIRA_API_TOKEN",
        url: "https://your-jira-instance.atlassian.net/rest/api/2/",
    };

    let issue_key = "ABC-123";
    let task_name = "";

    let result = create_task(&config, issue_key, task_name).await;
    assert!(result.is_err());
}

#[tokio::test]
async fn test_update_task_success() {
    let config = AgentConfig {
        token: "YOUR_JIRA_API_TOKEN",
        url: "https://your-jira-instance.atlassian.net/rest/api/2/",
    };

    let issue_key = "ABC-123";
    let task_id = 1234567890;
    let new_status = "In Progress";

    let response = Response::builder()
        .status(200)
        .body("{}".to_string())
        .unwrap();

    update_task(&config, issue_key, task_id, new_status).await.unwrap();
}

#[tokio::test]
async fn test_update_task_error() {
    let config = AgentConfig {
        token: "YOUR_JIRA_API_TOKEN",
        url: "https://your-jira-instance.atlassian.net/rest/api/2/",
    };

    let issue_key = "ABC-123";
    let task_id = 1234567890;
    let new_status = "";

    let result = update_task(&config, issue_key, task_id, new_status).await;
    assert!(result.is_err());
}

#[tokio::test]
async fn test_delete_task_success() {
    let config = AgentConfig {
        token: "YOUR_JIRA_API_TOKEN",
        url: "https://your-jira-instance.atlassian.net/rest/api/2/",
    };

    let issue_key = "ABC-123";
    let task_id = 1234567890;

    let response = Response::builder()
        .status(204)
        .body("{}".to_string())
        .unwrap();

    delete_task(&config, issue_key, task_id).await.unwrap();
}

#[tokio::test]
async fn test_delete_task_error() {
    let config = AgentConfig {
        token: "YOUR_JIRA_API_TOKEN",
        url: "https://your-jira-instance.atlassian.net/rest/api/2/",
    };

    let issue_key = "ABC-123";
    let task_id = 1234567890;

    let result = delete_task(&config, issue_key, task_id).await;
    assert!(result.is_err());
}