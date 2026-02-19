use std::io::{self, Write};
use reqwest;
use serde_json;

// Define a struct to represent a Jira issue
#[derive(Debug, Serialize)]
struct Issue {
    key: String,
    fields: Fields,
}

// Define a struct to represent the fields of an issue
#[derive(Debug, Serialize)]
struct Fields {
    summary: String,
    description: String,
    priority: Priority,
    status: Status,
}

// Define a struct to represent the priority of an issue
#[derive(Debug, Serialize)]
struct Priority {
    name: String,
}

// Define a struct to represent the status of an issue
#[derive(Debug, Serialize)]
struct Status {
    name: String,
}

// Function to create a new Jira issue
fn create_issue(jira_url: &str, key: &str, summary: &str, description: &str) -> Result<Issue, reqwest::Error> {
    let fields = Fields {
        summary: summary.to_string(),
        description: description.to_string(),
        priority: Priority { name: "High".to_string() },
        status: Status { name: "To Do".to_string() },
    };

    let issue_json = serde_json::to_string(&Issue {
        key: key.to_string(),
        fields,
    })?;

    let response = reqwest::post(jira_url)
        .header("Content-Type", "application/json")
        .body(issue_json)
        .send()?;

    if response.status().is_success() {
        Ok(response.json::<Issue>()?)
    } else {
        Err(reqwest::Error::from(response))
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let key = "RUST-12";
    let summary = "Integrate Rust Agent with Jira - tracking of activities";
    let description = "This is a test issue to track the progress of integrating Rust Agent with Jira.";

    match create_issue(jira_url, key, summary, description) {
        Ok(issue) => println!("Issue created: {:?}", issue),
        Err(e) => eprintln!("Error creating issue: {}", e),
    }

    Ok(())
}