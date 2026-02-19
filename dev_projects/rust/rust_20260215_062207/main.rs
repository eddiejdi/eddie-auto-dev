use reqwest;
use serde_json;

// Define a struct to represent a Jira issue
#[derive(Debug, Serialize)]
struct Issue {
    key: String,
    summary: String,
    description: String,
}

fn create_issue(jira_url: &str, username: &str, password: &str, issue: &Issue) -> Result<(), reqwest::Error> {
    let url = format!("{}/rest/api/2/issue", jira_url);
    let json_body = serde_json::to_string(issue)?;

    let response = reqwest::Client::new()
        .post(url)
        .basic_auth(username, password)
        .header("Content-Type", "application/json")
        .body(json_body)
        .send()?;

    if response.status().is_success() {
        Ok(())
    } else {
        Err(reqwest::Error::from(response))
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net";
    let username = "your-username";
    let password = "your-password";

    let issue = Issue {
        key: "TEST-123".to_string(),
        summary: "Test Jira Integration".to_string(),
        description: "This is a test to integrate Rust Agent with Jira.".to_string(),
    };

    create_issue(jira_url, username, password, &issue)?;

    println!("Issue created successfully!");

    Ok(())
}