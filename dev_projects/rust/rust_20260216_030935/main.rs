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
        let response = reqwest::post(
            &format!("{}rest/api/2/issue", self.base_url),
            headers! {["Authorization"] => format!("Basic {}", base64::encode(format!("{}:{}", self.auth_token, "xss")))},
        )
        .json(issue_data)
        .send()
        .await?;

        response.json().await
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-auth-token");

    let issue_data = json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Rust Agent Integration",
            "description": "This is a test for the Rust Agent integration with Jira.",
            "issuetype": {"name": "Bug"}
        }
    });

    let issue_response = jira_client.create_issue(issue_data).await?;

    println!("Issue created successfully: {:?}", issue_response);

    Ok(())
}