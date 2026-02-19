use crate::create_jira_issue;
use reqwest::{Error, Response};
use serde_json;

#[tokio::test]
async fn create_jira_issue_success() {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let issue_key = "YOUR-ISSUE-KEY";
    let summary = "Rust Agent Integration Test";
    let description = "This is a test for integrating Rust Agent with Jira.";
    let assignee = Some("user123");
    let priority_name = "High";
    let status_name = "In Progress";

    let priority = Priority {
        name: priority_name.to_string(),
    };

    let status = Status {
        name: status_name.to_string(),
    };

    let fields = Fields {
        summary,
        description,
        assignee,
        priority,
        status,
    };

    let issue = JiraIssue {
        key: issue_key.to_string(),
        fields,
    };

    match create_jira_issue(jira_url, issue).await {
        Ok(_) => assert!(true), // Success
        Err(e) => panic!("Error creating Jira issue: {}", e),
    }
}

#[tokio::test]
async fn create_jira_issue_failure() {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let issue_key = "YOUR-ISSUE-KEY";
    let summary = "Rust Agent Integration Test";
    let description = "This is a test for integrating Rust Agent with Jira.";
    let assignee = Some("user123");
    let priority_name = "High";
    let status_name = "In Progress";

    let priority = Priority {
        name: priority_name.to_string(),
    };

    let status = Status {
        name: status_name.to_string(),
    };

    let fields = Fields {
        summary,
        description,
        assignee,
        priority,
        status,
    };

    match create_jira_issue(jira_url, issue).await {
        Ok(_) => panic!("Expected error creating Jira issue"), // Failure
        Err(e) => assert!(e.is::<reqwest::Error>()), // Error type check
    }
}