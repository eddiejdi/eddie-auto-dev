use reqwest;
use serde_json::{self, Value};
use chrono::Utc;

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

    async fn create_issue(&self, issue_data: Value) -> Result<Value, reqwest::Error> {
        let response = self
            .client()
            .post(format!("{}rest/api/2/issue", &self.url))
            .header("Authorization", format!("Basic {}", base64::encode(&format!(":{}:{}", self.token, "x-www-form-urlencoded")))))
            .json(issue_data)
            .send()
            .await?;

        response.json().await
    }

    fn client(&self) -> reqwest::Client {
        reqwest::Client::new()
    }
}

#[derive(serde::Serialize)]
struct IssueData {
    fields: Value,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-api-token");

    let issue_data = IssueData {
        fields: serde_json::json!({
            "project": { "key": "YOUR-PROJECT" },
            "summary": "Example Rust Issue",
            "description": "This is an example of a Rust issue created using the Jira API.",
            "issuetype": { "name": "Bug" }
        }),
    };

    let response = jira_client.create_issue(issue_data).await?;

    println!("Issue created successfully: {:?}", response);

    Ok(())
}