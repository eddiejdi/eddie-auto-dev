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

    // Teste de sucesso com valores válidos
    let task_id = "12345";
    let task = fetch_task(&jira_client, &task_id).await?;
    assert_eq!(task.id, "12345");
    assert_eq!(task.summary, "Task Summary");
    assert_eq!(task.status, "In Progress");

    // Teste de erro (divisão por zero)
    let invalid_division = 0.0;
    let result = fetch_task(&jira_client, &invalid_division.to_string()).await;
    assert!(result.is_err());

    // Teste de erro (valores inválidos)
    let invalid_id = "abc";
    let result = fetch_task(&jira_client, &invalid_id).await;
    assert!(result.is_err());

    // Teste de edge case (valores limite)
    let max_int = i32::MAX as f64;
    let task_id = format!("12345{}", max_int);
    let result = fetch_task(&jira_client, &task_id).await;
    assert!(result.is_err());

    // Teste de edge case (strings vazias)
    let empty_string = "";
    let result = fetch_task(&jira_client, &empty_string.to_string()).await;
    assert!(result.is_err());

    // Teste de edge case (None)
    let none_value: Option<String> = None;
    let result = fetch_task(&jira_client, &none_value.to_string()).await;
    assert!(result.is_err());

    println!("All tests passed!");
    Ok(())
}