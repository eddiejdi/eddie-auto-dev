use serde::{Deserialize, Serialize};
use reqwest::Client;
use tokio;

#[derive(Serialize, Deserialize)]
struct JiraIssue {
    key: String,
    fields: Fields,
}

#[derive(Serialize, Deserialize)]
struct Fields {
    summary: String,
    description: Option<String>,
    status: Status,
}

#[derive(Serialize, Deserialize)]
struct Status {
    name: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let auth_token = "your-auth-token";

    let client = Client::new();

    // Create a new issue
    let new_issue = JiraIssue {
        key: "ABC-123".to_string(),
        fields: Fields {
            summary: "Test Issue".to_string(),
            description: Some("This is a test issue.".to_string()),
            status: Status { name: "To Do".to_string() },
        },
    };

    let response = client
        .post(jira_url)
        .header("Authorization", format!("Basic {}", auth_token))
        .json(&new_issue)
        .send()
        .await?;

    if response.status().is_success() {
        println!("Issue created successfully!");
    } else {
        eprintln!("Failed to create issue: {:?}", response.text());
    }

    Ok(())
}