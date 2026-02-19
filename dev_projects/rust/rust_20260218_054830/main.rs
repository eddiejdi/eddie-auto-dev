use reqwest;
use serde_json::{Value, Result};
use chrono::prelude::*;

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

    async fn get_issues(&self, query: &str) -> Result<Vec<Value>, reqwest::Error> {
        let url = format!("{}rest/api/2/search?jql={}", self.base_url, query);
        let response = reqwest::get(url).await?;
        response.json().await
    }

    async fn create_issue(&self, issue_data: &Value) -> Result<Value, reqwest::Error> {
        let url = format!("{}rest/api/2/issue", self.base_url);
        let response = reqwest::post(url)
            .header("Content-Type", "application/json")
            .bearer_auth(&self.auth_token)
            .body(serde_json::to_string(issue_data).unwrap())
            .send()
            .await?;
        response.json().await
    }
}

#[derive(Debug)]
struct Issue {
    key: String,
    fields: Value,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-auth-token");

    // Example query to get issues
    let query = "project=YOUR_PROJECT AND status IN (OPEN, IN_PROGRESS)";
    let issues = jira_client.get_issues(query).await?;

    for issue in issues {
        println!("Issue Key: {}", issue["key"].as_str().unwrap());
        println!("Fields: {:?}", issue["fields"]);
    }

    // Example of creating a new issue
    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT"},
            "summary": "Example Issue",
            "description": "This is an example issue created via Rust.",
            "issuetype": {"name": "Bug"}
        }
    });

    let new_issue = jira_client.create_issue(&issue_data).await?;

    println!("New Issue Key: {}", new_issue["key"].as_str().unwrap());

    Ok(())
}