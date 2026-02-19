use std::io::{self, Write};
use reqwest;
use serde_json;

// Define a struct to represent the Jira issue
#[derive(Debug, Serialize)]
struct Issue {
    key: String,
    fields: Fields,
}

// Define a struct to represent the Jira fields
#[derive(Debug, Serialize)]
struct Fields {
    summary: String,
    description: String,
    status: Status,
}

// Define a struct to represent the Jira status
#[derive(Debug, Serialize)]
struct Status {
    name: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create a new issue object
    let issue = Issue {
        key: "ABC-123".to_string(),
        fields: Fields {
            summary: "Rust Agent Integration with Jira".to_string(),
            description: "This is a test to integrate Rust Agent with Jira using the Jira REST API.".to_string(),
            status: Status {
                name: "To Do".to_string(),
            },
        },
    };

    // Serialize the issue object to JSON
    let json = serde_json::to_string(&issue)?;

    // Create a new client to interact with the Jira API
    let client = reqwest::Client::new();

    // Send a POST request to create a new issue in Jira
    let response = client.post("https://your-jira-instance.atlassian.net/rest/api/2/issue")
        .header("Content-Type", "application/json")
        .body(json)
        .send()?;

    // Check if the request was successful
    if response.status().is_success() {
        println!("Issue created successfully!");
    } else {
        let error_response = response.text()?;
        println!("Error creating issue: {}", error_response);
    }

    Ok(())
}