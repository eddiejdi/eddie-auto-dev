use reqwest;
use serde_json::Value;

// Define a struct to represent a Jira issue
#[derive(Debug, Deserialize)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

// Define a struct to represent a Rust Agent configuration
#[derive(Debug, Deserialize)]
struct AgentConfig {
    token: String,
    url: String,
}

// Define a struct to represent a task in the Jira issue
#[derive(Debug, Deserialize)]
struct Task {
    id: i64,
    name: String,
    description: Option<String>,
    status: String,
}

// Function to connect to Jira API and get issues
async fn fetch_issues(config: &AgentConfig) -> Result<Vec<Issue>, reqwest::Error> {
    let response = reqwest::get(&format!("{}rest/api/2/search", config.url))
        .header("Authorization", format!("Bearer {}", config.token))
        .send()
        .await?;

    if !response.status().is_success() {
        return Err(reqwest::Error::from(response));
    }

    let json: Value = response.json().await?;
    let issues: Vec<Issue> = serde_json::from_value(json["issues"].clone())?;

    Ok(issues)
}

// Function to create a new task in the Jira issue
async fn create_task(config: &AgentConfig, issue_key: String, task_name: &str) -> Result<(), reqwest::Error> {
    let response = reqwest::post(&format!("{}rest/api/2/task", config.url))
        .header("Authorization", format!("Bearer {}", config.token))
        .json(&serde_json!({
            "issue": issue_key,
            "name": task_name,
            "description": None,
            "status": "To Do",
        }))
        .send()
        .await?;

    if !response.status().is_success() {
        return Err(reqwest::Error::from(response));
    }

    Ok(())
}

// Function to update a task in the Jira issue
async fn update_task(config: &AgentConfig, issue_key: String, task_id: i64, new_status: &str) -> Result<(), reqwest::Error> {
    let response = reqwest::put(&format!("{}rest/api/2/task/{}", config.url, task_id))
        .header("Authorization", format!("Bearer {}", config.token))
        .json(&serde_json!({
            "status": new_status,
        }))
        .send()
        .await?;

    if !response.status().is_success() {
        return Err(reqwest::Error::from(response));
    }

    Ok(())
}

// Function to delete a task in the Jira issue
async fn delete_task(config: &AgentConfig, issue_key: String, task_id: i64) -> Result<(), reqwest::Error> {
    let response = reqwest::delete(&format!("{}rest/api/2/task/{}", config.url, task_id))
        .header("Authorization", format!("Bearer {}", config.token))
        .send()
        .await?;

    if !response.status().is_success() {
        return Err(reqwest::Error::from(response));
    }

    Ok(())
}

// Main function to run the Rust Agent
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let config = AgentConfig {
        token: "YOUR_JIRA_API_TOKEN",
        url: "https://your-jira-instance.atlassian.net/rest/api/2/",
    };

    // Fetch issues from Jira
    let issues = fetch_issues(&config).await?;

    for issue in issues {
        println!("Issue Key: {}", issue.key);
        println!("Summary: {}", issue.summary);
        println!("Status: {}", issue.status);

        // Create a new task in the issue
        create_task(&config, issue.key, "New Task").await?;

        // Update the status of the task
        update_task(&config, issue.key, 1234567890, "In Progress").await?;

        // Delete the task
        delete_task(&config, issue.key, 1234567890).await?;
    }

    Ok(())
}