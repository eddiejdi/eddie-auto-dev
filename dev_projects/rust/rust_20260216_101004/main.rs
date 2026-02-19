use reqwest;
use serde_json::Value;

// Define a struct to represent the Jira issue
#[derive(Debug)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

impl Issue {
    fn new(key: &str, summary: &str, status: &str) -> Self {
        Issue {
            key: key.to_string(),
            summary: summary.to_string(),
            status: status.to_string(),
        }
    }

    fn to_json(&self) -> Value {
        serde_json::json!({
            "key": self.key,
            "fields": {
                "summary": self.summary,
                "status": self.status
            }
        })
    }
}

// Define a struct to represent the Jira client
struct JiraClient {
    token: String,
}

impl JiraClient {
    fn new(token: &str) -> Self {
        JiraClient { token: token.to_string() }
    }

    async fn create_issue(&self, issue: Issue) -> Result<(), reqwest::Error> {
        let url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
        let response = reqwest::post(url)
            .header("Authorization", format!("Bearer {}", self.token))
            .json(issue.to_json())
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::from(response.text().await.unwrap()))
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let token = "your-jira-token";
    let client = JiraClient::new(token);

    let issue = Issue::new("TEST-123", "Test issue summary", "Open");

    client.create_issue(issue).await?;

    println!("Issue created successfully!");

    Ok(())
}