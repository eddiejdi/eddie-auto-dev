use reqwest;
use serde_json::Value;

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

    async fn create_issue(&self, issue_data: Value) -> Result<Value, reqwest::Error> {
        let url = format!("{}rest/api/2/issue", self.base_url);
        let headers = [("Authorization", &format!("Bearer {}", self.token))].into_iter().collect();
        reqwest::Client::new()
            .post(url)
            .headers(headers)
            .json(&issue_data)
            .send()
            .await?
            .text()
            .await
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-api-token");

    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent.",
            "issuetype": {"name": "Bug"}
        }
    });

    let response = jira_client.create_issue(issue_data).await?;

    println!("Issue created successfully: {}", response);

    Ok(())
}