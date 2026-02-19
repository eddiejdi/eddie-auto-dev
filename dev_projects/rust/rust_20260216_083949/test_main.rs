use std::error::Error;
use std::fs::File;
use std::io::{self, BufRead};
use serde_json::Value;

struct JiraClient {
    username: String,
    password: String,
}

impl JiraClient {
    fn new(username: &str, password: &str) -> Self {
        JiraClient {
            username: username.to_string(),
            password: password.to_string(),
        }
    }

    async fn post_issue(&self, issue_data: Value) -> Result<(), Box<dyn Error>> {
        let url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
        let client = reqwest::Client::new();
        let response = client.post(url)
            .header("Content-Type", "application/json")
            .basic_auth(&self.username, Some(&self.password))
            .json(issue_data)
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(format!("Failed to create issue: {}", response.text().await?).into());
        }

        Ok(())
    }
}

#[derive(serde::Deserialize)]
struct IssueData {
    project: String,
    summary: String,
    description: String,
    issuetype: String,
    assignee: Option<String>,
}

fn main() -> Result<(), Box<dyn Error>> {
    let jira_client = JiraClient::new("your-username", "your-password");

    let issue_data = IssueData {
        project: "YOUR_PROJECT_KEY".to_string(),
        summary: "Example issue".to_string(),
        description: "This is a test issue.".to_string(),
        issuetype: "Task".to_string(),
        assignee: Some("assignee-username".to_string()),
    };

    jira_client.post_issue(issue_data).await?;

    println!("Issue created successfully!");

    Ok(())
}

#[tokio::test]
async fn test_post_issue_success() {
    let jira_client = JiraClient::new("your-username", "your-password");
    let issue_data = IssueData {
        project: "YOUR_PROJECT_KEY".to_string(),
        summary: "Example issue".to_string(),
        description: "This is a test issue.".to_string(),
        issuetype: "Task".to_string(),
        assignee: Some("assignee-username".to_string()),
    };

    assert!(jira_client.post_issue(issue_data).await.is_ok());
}

#[tokio::test]
async fn test_post_issue_failure() {
    let jira_client = JiraClient::new("your-username", "your-password");
    let issue_data = IssueData {
        project: "YOUR_PROJECT_KEY".to_string(),
        summary: "Example issue".to_string(),
        description: "This is a test issue.".to_string(),
        issuetype: "Task".to_string(),
        assignee: Some("assignee-username".to_string()),
    };

    assert!(jira_client.post_issue(issue_data).await.is_err());
}