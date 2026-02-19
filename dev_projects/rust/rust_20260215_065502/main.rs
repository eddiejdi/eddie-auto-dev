use reqwest;
use serde_json::{self, Value};
use std::error::Error;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

impl JiraIssue {
    fn from_json(json_str: &str) -> Result<Self, Error> {
        let value: Value = serde_json::from_str(json_str)?;
        Ok(Self {
            key: value["key"].as_str().unwrap().to_string(),
            summary: value["fields"]["summary"].as_str().unwrap().to_string(),
            status: value["fields"]["status"]["name"].as_str().unwrap().to_string(),
        })
    }
}

#[derive(Debug)]
struct JiraClient {
    token: String,
    base_url: String,
}

impl JiraClient {
    fn new(token: &str, base_url: &str) -> Self {
        Self {
            token: token.to_string(),
            base_url: base_url.to_string(),
        }
    }

    async fn get_issue(&self, issue_key: &str) -> Result<JiraIssue, Error> {
        let url = format!("{}rest/api/2/issue/{}", self.base_url, issue_key);
        let response = reqwest::get(url).await?;
        if !response.status().is_success() {
            return Err(Error::from(response.text().await.unwrap()));
        }
        let json_str = response.text().await?;
        JiraIssue::from_json(&json_str)
    }
}

#[derive(Debug)]
struct CliApp {
    client: JiraClient,
}

impl CliApp {
    fn new(token: &str, base_url: &str) -> Self {
        Self {
            client: JiraClient::new(token, base_url),
        }
    }

    async fn run(&self) -> Result<(), Error> {
        println!("Enter issue key:");
        let mut input = String::new();
        std::io::stdin().read_line(&mut input).expect("Failed to read line");
        let issue_key = &input.trim()[..];

        let issue = self.client.get_issue(issue_key).await?;
        println!("Issue Key: {}", issue.key);
        println!("Summary: {}", issue.summary);
        println!("Status: {}", issue.status);

        Ok(())
    }
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    let token = "YOUR_JIRA_TOKEN";
    let base_url = "https://your-jira-instance.atlassian.net";

    let app = CliApp::new(token, base_url);
    app.run().await?;

    Ok(())
}