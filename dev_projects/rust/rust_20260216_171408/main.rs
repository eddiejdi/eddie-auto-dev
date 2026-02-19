use jira_client::JiraClient;
use serde_json::Value;

#[derive(Debug)]
struct JiraTask {
    id: String,
    summary: String,
    status: String,
}

async fn fetch_task(jira: &JiraClient, task_id: &str) -> Result<JiraTask, Box<dyn std::error::Error>> {
    let response = jira.get_issue(task_id).await?;
    Ok(response.as_object().unwrap().get("fields").unwrap().as_object().unwrap().clone())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-email@example.com", "your-api-token").await?;

    let task_id = "12345"; // Replace with the actual task ID
    let task = fetch_task(&jira_client, &task_id).await?;

    println!("Task: {}", task.summary);
    println!("Status: {}", task.status);

    Ok(())
}