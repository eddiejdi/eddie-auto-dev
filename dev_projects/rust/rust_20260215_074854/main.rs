use std::io::{self, Write};
use reqwest;
use serde_json;

struct JiraClient {
    url: String,
    token: String,
}

impl JiraClient {
    fn new(url: &str, token: &str) -> Self {
        JiraClient {
            url: url.to_string(),
            token: token.to_string(),
        }
    }

    async fn create_issue(&self, issue_data: serde_json::Value) -> Result<(), Box<dyn std::error::Error>> {
        let response = reqwest::post(&format!("{}rest/api/2/issue", self.url))
            .header("Authorization", format!("Bearer {}", self.token))
            .json(issue_data)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(format!("Failed to create issue: {}", response.text().await?).into())
        }
    }
}

#[derive(serde::Serialize)]
struct IssueData {
    project: String,
    summary: String,
    description: String,
    issuetype: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-api-token");

    let issue_data = IssueData {
        project: "YOUR_PROJECT_KEY".to_string(),
        summary: "Example issue".to_string(),
        description: "This is an example issue created by Rust Agent.".to_string(),
        issuetype: "Task".to_string(),
    };

    client.create_issue(issue_data).await?;

    println!("Issue created successfully!");

    Ok(())
}