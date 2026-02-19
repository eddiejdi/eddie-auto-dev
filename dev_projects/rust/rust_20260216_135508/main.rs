use reqwest::{Client, Response};
use serde_json::Value;

struct Jira {
    url: String,
    token: String,
}

impl Jira {
    fn new(url: &str, token: &str) -> Self {
        Jira {
            url: url.to_string(),
            token: token.to_string(),
        }
    }

    async fn create_issue(&self, issue_data: Value) -> Result<Response, reqwest::Error> {
        let client = Client::new();
        let response = client
            .post(&format!("{}rest/api/2/issue", self.url))
            .header("Authorization", format!("Bearer {}", self.token))
            .json(issue_data)
            .send()
            .await?;

        Ok(response)
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira = Jira::new("https://your-jira-instance.atlassian.net", "your-api-token");

    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR-PROJECT"},
            "summary": "Test issue",
            "description": "This is a test issue created by Rust Agent.",
            "issuetype": {"name": "Bug"}
        }
    });

    let response = jira.create_issue(issue_data).await?;

    println!("Issue created successfully: {}", response.url());

    Ok(())
}