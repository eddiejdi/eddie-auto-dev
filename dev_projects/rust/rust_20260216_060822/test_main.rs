use std::io::{self, Write};
use reqwest;
use serde_json;

struct JiraClient {
    base_url: String,
}

impl JiraClient {
    fn new(base_url: &str) -> Self {
        JiraClient { base_url: base_url.to_string() }
    }

    async fn create_issue(&self, issue_data: &serde_json::Value) -> Result<(), reqwest::Error> {
        let response = self
            .send_request("POST", "/rest/api/2/issue", issue_data)
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::from(response))
        }
    }

    async fn send_request(&self, method: &str, endpoint: &str, body: &serde_json::Value) -> Result<reqwest::Response, reqwest::Error> {
        let url = format!("{}{}", self.base_url, endpoint);
        let client = reqwest::Client::new();

        match method {
            "POST" => client.post(url).json(body).send(),
            _ => client.get(url).json(body).send(),
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
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net");

    let issue_data = IssueData {
        project: "YOUR_PROJECT_KEY".to_string(),
        summary: "Example Task".to_string(),
        description: "This is an example task created by Rust Agent.".to_string(),
        issuetype: "Task".to_string(),
    };

    jira_client.create_issue(&serde_json::to_value(issue_data)?)?;

    println!("Issue created successfully!");

    Ok(())
}