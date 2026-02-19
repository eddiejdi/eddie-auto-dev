use std::io::{self, Write};
use serde_json::Value;
use reqwest;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

impl JiraIssue {
    fn new(key: &str, summary: &str, status: &str) -> Self {
        JiraIssue {
            key: key.to_string(),
            summary: summary.to_string(),
            status: status.to_string(),
        }
    }

    fn update_status(&mut self, new_status: &str) {
        self.status = new_status.to_string();
    }
}

#[derive(Debug)]
struct JiraClient {
    base_url: String,
    auth_token: String,
}

impl JiraClient {
    fn new(base_url: &str, auth_token: &str) -> Self {
        JiraClient {
            base_url: base_url.to_string(),
            auth_token: auth_token.to_string(),
        }
    }

    async fn create_issue(&self, issue: &JiraIssue) -> Result<(), reqwest::Error> {
        let response = reqwest::post(format!(
            "{}rest/api/2/issue",
            self.base_url
        ))
        .header("Authorization", format!("Basic {}", base64::encode(&format!("{}:{}", self.auth_token, issue.key))))
        .json(issue)
        .send()
        .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::from(response))
        }
    }

    async fn update_issue_status(&self, key: &str, new_status: &str) -> Result<(), reqwest::Error> {
        let issue = JiraIssue::new(key, "Updated by Rust Agent", new_status);
        self.create_issue(&issue).await
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = JiraClient::new("https://your-jira-instance.atlassian.net/rest/api/2/", "your-auth-token");
    let issue = JiraIssue::new("ABC-123", "New task from Rust Agent", "To do");

    // Create the issue
    assert_eq!(client.create_issue(&issue).await.is_ok(), true);

    // Update the status of the issue
    assert_eq!(client.update_issue_status(&issue.key, "In Progress").await.is_ok(), true);

    println!("Task created and updated successfully!");

    Ok(())
}