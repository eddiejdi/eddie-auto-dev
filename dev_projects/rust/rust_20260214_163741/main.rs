use reqwest;
use serde_json::Value;

// Define a struct to represent a Jira issue
struct Issue {
    key: String,
    summary: String,
    status: String,
}

// Function to create an issue in Jira
async fn create_issue(issue: &Issue) -> Result<(), Box<dyn std::error::Error>> {
    let url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let client = reqwest::Client::new();
    let json_body = serde_json::to_string(&issue).unwrap();

    let response = client.post(url)
        .header("Content-Type", "application/json")
        .body(json_body)
        .send()
        .await?;

    if response.status().is_success() {
        Ok(())
    } else {
        Err(format!("Failed to create issue: {}", response.text().await.unwrap()).into())
    }
}

// Function to monitor a task in Jira
async fn monitor_task(issue_key: &str) -> Result<(), Box<dyn std::error::Error>> {
    let url = "https://your-jira-instance.atlassian.net/rest/api/2/issue/{}/log";
    let client = reqwest::Client::new();
    let response = client.get(url)
        .query(&[("fields", "status")])
        .send()
        .await?;

    if response.status().is_success() {
        let json_response: Value = serde_json::from_str(&response.text().await.unwrap()).unwrap();
        let status = json_response["fields"]["status"]["name"].as_str().unwrap();

        println!("Task {} is now in status {}", issue_key, status);

        Ok(())
    } else {
        Err(format!("Failed to monitor task: {}", response.text().await.unwrap()).into())
    }
}

// Main function
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create an issue in Jira
    let issue = Issue {
        key: "RUST-12".to_string(),
        summary: "Implement Rust Agent with Jira tracking",
        status: "To Do".to_string(),
    };
    create_issue(&issue).await?;

    // Monitor the task in Jira
    monitor_task("RUST-12").await?;

    Ok(())
}