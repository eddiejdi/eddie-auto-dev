use reqwest;
use serde_json::Value;

// Define a struct to represent a Jira issue
#[derive(Debug, Deserialize)]
struct Issue {
    key: String,
    summary: String,
    description: String,
}

// Define a struct to represent the response from the Jira API
#[derive(Debug, Deserialize)]
struct JiraResponse {
    issues: Vec<Issue>,
}

// Function to create an issue in Jira
async fn create_issue(jira_url: &str, username: &str, password: &str, summary: &str, description: &str) -> Result<JiraResponse, reqwest::Error> {
    let url = format!("{}rest/api/2/issue", jira_url);
    let json_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": summary,
            "description": description
        }
    });

    let response = reqwest::Client::new()
        .post(url)
        .basic_auth(username, Some(password))
        .header("Content-Type", "application/json")
        .body(json_data.to_string())
        .send()
        .await?;

    if response.status().is_success() {
        Ok(response.json::<JiraResponse>().await?)
    } else {
        Err(reqwest::Error::from(response.text().await.unwrap()))
    }
}

// Function to list all issues in Jira
async fn list_issues(jira_url: &str, username: &str, password: &str) -> Result<Vec<Issue>, reqwest::Error> {
    let url = format!("{}rest/api/2/search", jira_url);
    let json_data = serde_json::json!({
        "jql": "project=YOUR_PROJECT_KEY",
        "fields": ["key", "summary", "description"]
    });

    let response = reqwest::Client::new()
        .post(url)
        .basic_auth(username, Some(password))
        .header("Content-Type", "application/json")
        .body(json_data.to_string())
        .send()
        .await?;

    if response.status().is_success() {
        Ok(response.json::<JiraResponse>().await?.issues)
    } else {
        Err(reqwest::Error::from(response.text().await.unwrap()))
    }
}

// Main function to demonstrate the usage of the Rust Agent with Jira Integration
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Replace with your Jira URL, username, and password
    let jira_url = "https://your-jira-instance.atlassian.net";
    let username = "your-username";
    let password = "your-password";

    // Create an issue in Jira
    let create_response = create_issue(jira_url, username, password, "Task 1", "This is a test task.").await?;
    println!("Created issue: {:?}", create_response);

    // List all issues in Jira
    let list_response = list_issues(jira_url, username, password).await?;
    println!("List of issues: {:?}", list_response);

    Ok(())
}