use reqwest;
use serde_json::Value;

// Define a struct to represent the Jira project configuration
#[derive(Debug)]
struct ProjectConfig {
    name: String,
    key: String,
}

// Define a struct to represent the Jira issue
#[derive(Debug)]
struct Issue {
    id: String,
    summary: String,
    status: String,
}

// Define a struct to represent the Jira project
#[derive(Debug)]
struct Project {
    config: ProjectConfig,
    issues: Vec<Issue>,
}

// Function to fetch all issues from a Jira project using the Jira API
async fn fetch_issues(project_key: &str) -> Result<Vec<Issue>, reqwest::Error> {
    let url = format!("https://api.atlassian.com/jira/rest/api/3/project/{}/issue", project_key);
    let response = reqwest::get(&url).await?;
    if !response.status().is_success() {
        return Err(reqwest::Error::from(response));
    }
    Ok(response.json::<Vec<Issue>>().await?)
}

// Function to create a new issue in a Jira project using the Jira API
async fn create_issue(project_key: &str, summary: &str, description: &str) -> Result<String, reqwest::Error> {
    let url = format!("https://api.atlassian.com/jira/rest/api/3/project/{}/issue", project_key);
    let body = serde_json::json!({
        "fields": {
            "project": { "key": project_key },
            "summary": summary,
            "description": description
        }
    });
    let response = reqwest::post(&url, json_body).await?;
    if !response.status().is_success() {
        return Err(reqwest::Error::from(response));
    }
    Ok(response.text().await?)
}

// Main function to demonstrate the usage of the Jira API
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Define project configuration
    let config = ProjectConfig {
        name: "MyProject".to_string(),
        key: "MYPROJECT".to_string(),
    };

    // Fetch all issues from the project
    let issues = fetch_issues(&config.key).await?;

    // Print fetched issues
    println!("Fetched Issues:");
    for issue in &issues {
        println!("{:?}", issue);
    }

    // Create a new issue
    let summary = "New Task";
    let description = "This is a new task to be completed.";
    let new_issue_id = create_issue(&config.key, summary, description).await?;

    println!("Created Issue ID: {}", new_issue_id);

    Ok(())
}