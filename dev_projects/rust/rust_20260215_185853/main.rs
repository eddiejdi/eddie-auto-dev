use reqwest;
use serde_json::Value;

struct JiraClient {
    base_url: String,
}

impl JiraClient {
    fn new(base_url: String) -> Self {
        JiraClient { base_url }
    }

    async fn create_issue(&self, issue_data: Value) -> Result<Value, reqwest::Error> {
        let response = self
            .base_url
            .clone()
            .parse::<reqwest::Url>()
            .unwrap()
            .join("rest/api/2/issue")
            .unwrap()
            .build()
            .unwrap();

        let client = reqwest::Client::new();
        client.post(response).json(issue_data).send().await
    }
}

#[tokio::main]
async fn main() {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net".to_string());

    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Test Issue",
            "description": "This is a test issue created using Rust and Jira API.",
            "issuetype": {"name": "Bug"}
        }
    });

    match jira_client.create_issue(issue_data).await {
        Ok(response) => println!("Issue created: {:?}", response),
        Err(e) => eprintln!("Error creating issue: {}", e),
    }
}