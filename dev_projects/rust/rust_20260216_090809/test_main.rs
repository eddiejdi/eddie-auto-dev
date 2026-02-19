use std::io::{self, Write};
use reqwest;
use serde_json;

// Define a struct to hold Jira issue details
#[derive(serde::Deserialize)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Set up the Jira API endpoint and authentication token
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let auth_token = "your-auth-token";

    // Create a new client to make HTTP requests
    let client = reqwest::Client::new();

    // Define the issue data to be sent to Jira
    let issue_data = Issue {
        key: "TEST-1".to_string(),
        summary: "Test issue for Rust Agent integration".to_string(),
        status: "Open".to_string(),
    };

    // Serialize the issue data to JSON format
    let json_data = serde_json::to_string(&issue_data)?;

    // Make a POST request to create the issue on Jira
    let response = client.post(jira_url)
        .header("Authorization", format!("Basic {}", auth_token))
        .header("Content-Type", "application/json")
        .body(json_data)
        .send()?;

    // Check if the request was successful
    if response.status().is_success() {
        println!("Issue created successfully");
    } else {
        eprintln!("Failed to create issue: {}", response.text()?);
    }

    Ok(())
}

// Test cases for the main function
#[cfg(test)]
mod tests {
    use super::*;

    // Test case for successful creation of an issue
    #[test]
    fn test_create_issue_success() {
        let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
        let auth_token = "your-auth-token";

        // Create a new client to make HTTP requests
        let client = reqwest::Client::new();

        // Define the issue data to be sent to Jira
        let issue_data = Issue {
            key: "TEST-1".to_string(),
            summary: "Test issue for Rust Agent integration".to_string(),
            status: "Open".to_string(),
        };

        // Serialize the issue data to JSON format
        let json_data = serde_json::to_string(&issue_data)?;

        // Make a POST request to create the issue on Jira
        let response = client.post(jira_url)
            .header("Authorization", format!("Basic {}", auth_token))
            .header("Content-Type", "application/json")
            .body(json_data)
            .send()?;

        // Check if the request was successful
        assert!(response.status().is_success(), "Failed to create issue");
    }

    // Test case for error handling in creating an issue
    #[test]
    fn test_create_issue_error() {
        let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
        let auth_token = "your-auth-token";

        // Create a new client to make HTTP requests
        let client = reqwest::Client::new();

        // Define the issue data to be sent to Jira
        let issue_data = Issue {
            key: "TEST-1".to_string(),
            summary: "Test issue for Rust Agent integration".to_string(),
            status: "Open".to_string(),
        };

        // Serialize the issue data to JSON format
        let json_data = serde_json::to_string(&issue_data)?;

        // Make a POST request to create the issue on Jira with an invalid token
        let response = client.post(jira_url)
            .header("Authorization", "Basic invalid-token")
            .header("Content-Type", "application/json")
            .body(json_data)
            .send()?;

        // Check if the request was unsuccessful
        assert!(!response.status().is_success(), "Request should have failed");
    }
}