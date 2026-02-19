use reqwest;
use serde_json;

struct JiraClient {
    base_url: String,
}

impl JiraClient {
    fn new(base_url: &str) -> Self {
        JiraClient { base_url }
    }

    async fn create_issue(&self, issue_data: serde_json::Value) -> Result<(), reqwest::Error> {
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
        let response = client.post(response).json(issue_data).send().await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::from(response))
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net");

    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent",
            "issuetype": {"name": "Bug"}
        }
    });

    match jira_client.create_issue(issue_data).await {
        Ok(_) => println!("Issue created successfully"),
        Err(e) => eprintln!("Error creating issue: {}", e),
    }

    Ok(())
}