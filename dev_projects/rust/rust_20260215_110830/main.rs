use reqwest::Client;
use serde_json::{Value, Map};
use std::error::Error;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn Error>> {
    let client = Client::new();
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/search";
    let query = "project=YOUR_PROJECT_KEY AND status IN (OPEN, IN_PROGRESS)";

    let response = client.get(jira_url)
        .query(&[("jql", query)])
        .send()?;

    if response.status().is_success() {
        let json: Value = response.json()?;
        let issues: Vec<JiraIssue> = serde_json::from_value(json["issues"].clone())?;

        for issue in issues {
            println!("Key: {}", issue.key);
            println!("Summary: {}", issue.summary);
            println!("Status: {}", issue.status);
            println!();
        }
    } else {
        eprintln!("Failed to retrieve Jira issues: {}", response.text()?);
    }

    Ok(())
}