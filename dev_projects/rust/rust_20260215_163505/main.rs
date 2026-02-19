use reqwest;
use serde_json::Value;
use std::env;

struct JiraClient {
    jira_base_url: String,
}

impl JiraClient {
    fn new(jira_base_url: &str) -> Self {
        JiraClient {
            jira_base_url: jira_base_url.to_string(),
        }
    }

    async fn create_issue(&self, issue_data: Value) -> Result<String, reqwest::Error> {
        let response = self
            .jira_base_url
            .clone()
            .parse::<reqwest::Url>()
            .unwrap()
            .join("/rest/api/2/issue")
            .unwrap()
            .build()
            .unwrap();

        let client = reqwest::Client::new();
        let response = client.post(response).json(issue_data).send().await?;

        Ok(response.text().await?)
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_base_url = env::var("JIRA_BASE_URL")?;
    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent",
            "issuetype": {"name": "Bug"}
        }
    });

    let client = JiraClient::new(&jira_base_url);
    let response = client.create_issue(issue_data).await?;

    println!("Issue created: {}", response);

    Ok(())
}