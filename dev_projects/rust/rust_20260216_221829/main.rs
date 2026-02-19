use reqwest;
use serde_json::Value;

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

    async fn create_issue(&self, issue_data: Value) -> Result<Value, reqwest::Error> {
        let response = self
            .client()
            .post(format!("{}rest/api/2/issue", &self.base_url))
            .header("Content-Type", "application/json")
            .header("Authorization", format!("Basic {}", base64::encode(&format!("{}:{}", &self.auth_token, &self.base_url)))))
            .body(issue_data.to_string())
            .send()
            .await?;

        response.json().await
    }

    fn client(&self) -> reqwest::Client {
        reqwest::Client::new()
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-auth-token");

    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Test issue",
            "description": "This is a test issue created using Rust and Jira API",
            "issuetype": {"name": "Bug"}
        }
    });

    let response = jira_client.create_issue(issue_data).await?;

    println!("Issue created successfully: {:?}", response);

    Ok(())
}