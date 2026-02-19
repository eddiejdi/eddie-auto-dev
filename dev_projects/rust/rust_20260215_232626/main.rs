use std::io::{self, Write};
use reqwest::Client;
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    description: String,
}

impl JiraIssue {
    fn new(key: &str, summary: &str, description: &str) -> Self {
        Self {
            key: key.to_string(),
            summary: summary.to_string(),
            description: description.to_string(),
        }
    }

    fn create(&self, client: &Client) -> Result<(), Box<dyn std::error::Error>> {
        let url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
        let json = serde_json::json!({
            "fields": {
                "project": {"key": "YOUR_PROJECT_KEY"},
                "summary": self.summary,
                "description": self.description,
                "issuetype": {"name": "Task"}
            }
        });

        client.post(url)
            .header("Content-Type", "application/json")
            .json(&json)
            .send()?;

        Ok(())
    }
}

#[derive(Debug)]
struct JiraClient {
    client: Client,
}

impl JiraClient {
    fn new(base_url: &str) -> Self {
        Self {
            client: Client::new(),
        }
    }

    async fn create_issue(&self, issue: &JiraIssue) -> Result<(), Box<dyn std::error::Error>> {
        let response = self.client.create_issue(issue).await?;
        println!("Issue created with key: {}", response.id);
        Ok(())
    }
}

#[derive(Debug)]
struct JiraCli {
    client: JiraClient,
}

impl JiraCli {
    fn new(base_url: &str) -> Self {
        Self {
            client: JiraClient::new(base_url),
        }
    }

    async fn create_issue(&self, issue: &JiraIssue) -> Result<(), Box<dyn std::error::Error>> {
        self.client.create_issue(issue).await
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let base_url = "https://your-jira-instance.atlassian.net";
    let client = JiraClient::new(base_url);

    let issue = JiraIssue::new("TEST-123", "Implement Rust Agent with Jira tracking", "Track issues using Rust Agent");

    client.create_issue(&issue).await?;

    Ok(())
}