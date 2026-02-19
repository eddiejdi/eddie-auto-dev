use std::io::{self, Write};
use reqwest;
use serde_json;

// Define a struct to represent a Jira issue
#[derive(Deserialize)]
struct Issue {
    key: String,
    fields: Fields,
}

// Define a struct to represent the fields of an issue
#[derive(Deserialize)]
struct Fields {
    description: Option<String>,
    status: Status,
}

// Define a struct to represent the status of an issue
#[derive(Deserialize)]
struct Status {
    name: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Set up Jira API endpoint and credentials
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let username = "your-username";
    let password = "your-password";

    // Create a new client to make HTTP requests
    let client = reqwest::Client::new();

    // Define the issue data to be sent
    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Example issue",
            "description": "This is a test issue.",
            "status": {"name": "To Do"}
        }
    });

    // Send the POST request to create the issue
    let response = client.post(jira_url)
        .basic_auth(username, Some(password))
        .json(&issue_data)
        .send()?;

    // Check if the request was successful
    if response.status().is_success() {
        println!("Issue created successfully!");
    } else {
        println!("Failed to create issue: {}", response.text()?);
    }

    Ok(())
}