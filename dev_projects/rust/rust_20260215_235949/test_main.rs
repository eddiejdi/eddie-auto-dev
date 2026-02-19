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

// Test case for create_issue function
#[tokio::test]
async fn test_create_issue_success() {
    let jira_url = "https://your-jira-url.atlassian.net";
    let username = "your-username";
    let password = "your-password";
    let summary = "New Rust Issue";
    let description = "This is a test issue for the Rust Agent.";

    let response = create_issue(jira_url, username, password, summary, description).await.unwrap();

    assert_eq!(response.issues.len(), 1);
    assert_eq!(response.issues[0].fields.summary, summary);
    assert_eq!(response.issues[0].fields.description, description);
}

// Test case for create_issue function with invalid input
#[tokio::test]
async fn test_create_issue_invalid_input() {
    let jira_url = "https://your-jira-url.atlassian.net";
    let username = "your-username";
    let password = "your-password";

    // Invalid summary
    let response = create_issue(jira_url, username, password, "", description).await.unwrap();
    assert_eq!(response.issues.len(), 0);

    // Invalid description
    let response = create_issue(jira_url, username, password, summary, "");
    assert_eq!(response.issues.len(), 0);
}

// Test case for list_issues function
#[tokio::test]
async fn test_list_issues_success() {
    let jira_url = "https://your-jira-url.atlassian.net";
    let username = "your-username";
    let password = "your-password";

    let response = list_issues(jira_url, username, password).await.unwrap();

    assert_eq!(response.issues.len(), 0); // Assuming no issues are created yet
}

// Test case for list_issues function with invalid input
#[tokio::test]
async fn test_list_issues_invalid_input() {
    let jira_url = "https://your-jira-url.atlassian.net";
    let username = "your-username";
    let password = "your-password";

    // Invalid JQL query
    let response = list_issues(jira_url, username, password, "project = YOUR_PROJECT_KEY", "").await.unwrap();
    assert_eq!(response.issues.len(), 0);
}