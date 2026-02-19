use std::io::{self, Write};
use reqwest;
use serde_json;

struct JiraClient {
    base_url: String,
    token: String,
}

impl JiraClient {
    fn new(base_url: &str, token: &str) -> Self {
        JiraClient {
            base_url: base_url.to_string(),
            token: token.to_string(),
        }
    }

    async fn create_issue(&self, issue_data: serde_json::Value) -> Result<(), reqwest::Error> {
        let url = format!("{}rest/api/2/issue", self.base_url);
        let response = reqwest::post(url)
            .header("Authorization", format!("Basic {}", base64::encode(format!(":{}:{}", self.token, "jira"))))
            .json(issue_data)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::from(response.text().await.unwrap()))
        }
    }

    async fn get_issues(&self) -> Result<Vec<serde_json::Value>, reqwest::Error> {
        let url = format!("{}rest/api/2/search", self.base_url);
        let response = reqwest::get(url)
            .header("Authorization", format!("Basic {}", base64::encode(format!(":{}:{}", self.token, "jira"))))
            .send()
            .await?;

        if response.status().is_success() {
            Ok(response.json::<Vec<serde_json::Value>>().await?)
        } else {
            Err(reqwest::Error::from(response.text().await.unwrap()))
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
    let client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-api-token");

    let issue_data = IssueData {
        project: "YOUR_PROJECT_KEY".to_string(),
        summary: "Example Task".to_string(),
        description: "This is an example task created by Rust Agent.".to_string(),
        issuetype: "TASK".to_string(),
    };

    client.create_issue(issue_data).await?;

    println!("Issue created successfully!");

    Ok(())
}