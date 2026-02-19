use std::io::{self, Write};
use reqwest;
use serde_json;

#[derive(Debug)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut client = reqwest::Client::new();

    // Simula uma requisição para Jira
    let response = client.get("https://your-jira-instance.atlassian.net/rest/api/2/search")
        .query(&[("jql", "project = YourProjectKey")])
        .send()?;

    if !response.status().is_success() {
        return Err(format!("Failed to fetch issues: {}", response.text()).into());
    }

    let json_response = response.json::<serde_json::Value>()?;
    let issues: Vec<Issue> = serde_json::from_value(json_response["issues"].clone())?;

    // Imprime informações dos problemas
    for issue in issues {
        writeln!(
            "Issue Key: {}, Summary: {}, Status: {}",
            issue.key, issue.summary, issue.status
        )?;
    }

    Ok(())
}