use reqwest::Client;
use serde_json::{Value, from_str};
use std::env;

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

    async fn get_issues(&self) -> Result<Vec<Value>, reqwest::Error> {
        let client = Client::new();
        let response = client
            .get(&format!("{}rest/api/2/search", self.url))
            .header("Authorization", format!("Basic {}", base64::encode(format!(":{}:{}", self.token, "xss"))))
            .send()
            .await?;

        if response.status().is_success() {
            let body = response.text().await?;
            Ok(from_str(&body).unwrap())
        } else {
            Err(reqwest::Error::from(response.status()))
        }
    }

    async fn create_issue(&self, issue: &Value) -> Result<(), reqwest::Error> {
        let client = Client::new();
        let response = client
            .post(&format!("{}rest/api/2/issue", self.url))
            .header("Authorization", format!("Basic {}", base64::encode(format!(":{}:{}", self.token, "xss"))))
            .json(issue)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::from(response.status()))
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira = Jira::new("https://your-jira-instance.atlassian.net", "your-api-token");

    // Example issue creation
    let issue = json!({
        "fields": {
            "project": {"key": "YOUR-PROJECT"},
            "summary": "Test issue",
            "description": "This is a test issue created by Rust Agent.",
            "issuetype": {"name": "Bug"}
        }
    });

    jira.create_issue(&issue).await?;

    println!("Issue created successfully.");

    Ok(())
}