use reqwest;
use serde_json;

// Define a struct to represent a Jira issue
#[derive(Debug, Deserialize)]
struct Issue {
    key: String,
    fields: Fields,
}

// Define a struct to represent the fields of an issue
#[derive(Debug, Deserialize)]
struct Fields {
    summary: String,
    description: String,
}

// Define a struct to represent the response from the Jira API
#[derive(Debug, Deserialize)]
struct Response {
    issues: Vec<Issue>,
}

// Function to create a new issue in Jira
async fn create_issue(jira_url: &str, username: &str, password: &str, summary: &str, description: &str) -> Result<Response, reqwest::Error> {
    let client = reqwest::Client::new();
    let url = format!("{}rest/api/2/issue", jira_url);

    let payload = serde_json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": summary,
            "description": description
        }
    });

    let response = client.post(url)
        .basic_auth(username, password)
        .json(&payload)
        .send()
        .await?;

    Ok(response.json().await?)
}

// Function to list all issues in Jira
async fn list_issues(jira_url: &str, username: &str, password: &str) -> Result<Response, reqwest::Error> {
    let client = reqwest::Client::new();
    let url = format!("{}rest/api/2/search", jira_url);

    let payload = serde_json!({
        "jql": "project = YOUR_PROJECT_KEY"
    });

    let response = client.post(url)
        .basic_auth(username, password)
        .json(&payload)
        .send()
        .await?;

    Ok(response.json().await?)
}

fn main() {
    // Replace with your Jira URL, username, and password
    let jira_url = "https://your-jira-url.atlassian.net";
    let username = "your-username";
    let password = "your-password";

    // Create a new issue
    match create_issue(jira_url, username, password, "New Rust Issue", "This is a test issue for the Rust Agent.") {
        Ok(response) => println!("Created issue: {:?}", response),
        Err(e) => eprintln!("Error creating issue: {}", e),
    }

    // List all issues
    match list_issues(jira_url, username, password) {
        Ok(response) => println!("List of issues: {:?}", response),
        Err(e) => eprintln!("Error listing issues: {}", e),
    }
}