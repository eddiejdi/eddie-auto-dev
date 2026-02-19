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
    description: String,
    status: Status,
}

// Define a struct to represent the status of an issue
#[derive(Deserialize)]
struct Status {
    name: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Set up the Jira API endpoint and authentication token
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/3/issue";
    let auth_token = "your-auth-token";

    // Create a new client to make HTTP requests
    let client = reqwest::Client::new();

    // Define the issue data to be created
    let issue_data = serde_json!({
        "fields": {
            "project": {
                "key": "YOUR_PROJECT_KEY"
            },
            "summary": "New Rust Agent Integration",
            "description": "This is a new integration of Rust Agent with Jira.",
            "issuetype": {
                "name": "Bug"
            }
        }
    });

    // Make a POST request to create the issue
    let response = client.post(jira_url)
        .header("Authorization", format!("Basic {}", auth_token))
        .json(&issue_data)
        .send()?;

    // Check if the request was successful
    if response.status().is_success() {
        println!("Issue created successfully: {}", response.text()?);
    } else {
        eprintln!("Failed to create issue: {}", response.text()?);
    }

    Ok(())
}