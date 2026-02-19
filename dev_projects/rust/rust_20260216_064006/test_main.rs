use reqwest;
use serde_json::Value;

// Define a struct to represent a task in Jira
#[derive(Debug, Deserialize)]
struct Task {
    id: String,
    summary: String,
    status: String,
}

// Function to create a new task in Jira
async fn create_task(jira_url: &str, username: &str, password: &str, project_key: &str, summary: &str) -> Result<Task, reqwest::Error> {
    let url = format!("{}rest/api/2/issue", jira_url);
    let json = serde_json::json!({
        "fields": {
            "project": { "key": project_key },
            "summary": summary,
            "description": "Created by Rust Agent",
            "issuetype": { "name": "Task" }
        }
    });

    let response = reqwest::Client::new()
        .post(url)
        .basic_auth(username, Some(password))
        .json(&json)
        .send()
        .await?;

    if response.status().is_success() {
        Ok(response.json::<Task>().await?)
    } else {
        Err(reqwest::Error::from(response.text().await.unwrap()))
    }
}

// Function to update a task in Jira
async fn update_task(jira_url: &str, username: &str, password: &str, issue_id: &str, summary: &str) -> Result<Task, reqwest::Error> {
    let url = format!("{}rest/api/2/issue/{}/update", jira_url, issue_id);
    let json = serde_json::json!({
        "fields": {
            "summary": summary
        }
    });

    let response = reqwest::Client::new()
        .put(url)
        .basic_auth(username, Some(password))
        .json(&json)
        .send()
        .await?;

    if response.status().is_success() {
        Ok(response.json::<Task>().await?)
    } else {
        Err(reqwest::Error::from(response.text().await.unwrap()))
    }
}

// Function to delete a task in Jira
async fn delete_task(jira_url: &str, username: &str, password: &str, issue_id: &str) -> Result<(), reqwest::Error> {
    let url = format!("{}rest/api/2/issue/{}/delete", jira_url, issue_id);
    let response = reqwest::Client::new()
        .delete(url)
        .basic_auth(username, Some(password))
        .send()
        .await?;

    if response.status().is_success() {
        Ok(())
    } else {
        Err(reqwest::Error::from(response.text().await.unwrap()))
    }
}

// Function to list all tasks in a project
async fn list_tasks(jira_url: &str, username: &str, password: &str, project_key: &str) -> Result<Vec<Task>, reqwest::Error> {
    let url = format!("{}rest/api/2/search?jql=project={} AND issuetype=Task", jira_url, project_key);
    let response = reqwest::Client::new()
        .get(url)
        .basic_auth(username, Some(password))
        .send()
        .await?;

    if response.status().is_success() {
        Ok(response.json::<Value>().as_array().unwrap().iter().map(|item| item.as_object().unwrap()).collect())
    } else {
        Err(reqwest::Error::from(response.text().await.unwrap()))
    }
}

// Main function to demonstrate the usage of the functions
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_task() {
        let jira_url = "https://your-jira-instance.atlassian.net";
        let username = "your-username";
        let password = "your-password";
        let project_key = "YOUR-PROJECT-KEY";
        let summary = "Test Task";

        match create_task(&jira_url, &username, &password, &project_key, &summary).await {
            Ok(task) => println!("Created task: {:?}", task),
            Err(e) => eprintln!("Error creating task: {}", e),
        }
    }

    #[tokio::test]
    async fn test_update_task() {
        let jira_url = "https://your-jira-instance.atlassian.net";
        let username = "your-username";
        let password = "your-password";
        let issue_id = "YOUR-ISSUE-ID";
        let summary = "Updated Task";

        match update_task(&jira_url, &username, &password, &issue_id, &summary).await {
            Ok(task) => println!("Updated task: {:?}", task),
            Err(e) => eprintln!("Error updating task: {}", e),
        }
    }

    #[tokio::test]
    async fn test_delete_task() {
        let jira_url = "https://your-jira-instance.atlassian.net";
        let username = "your-username";
        let password = "your-password";
        let issue_id = "YOUR-ISSUE-ID";

        match delete_task(&jira_url, &username, &password, &issue_id).await {
            Ok(_) => println!("Task deleted successfully"),
            Err(e) => eprintln!("Error deleting task: {}", e),
        }
    }

    #[tokio::test]
    async fn test_list_tasks() {
        let jira_url = "https://your-jira-instance.atlassian.net";
        let username = "your-username";
        let password = "your-password";
        let project_key = "YOUR-PROJECT-KEY";

        match list_tasks(&jira_url, &username, &password, &project_key).await {
            Ok(tasks) => println!("Tasks in project: {:?}", tasks),
            Err(e) => eprintln!("Error listing tasks: {}", e),
        }
    }
}