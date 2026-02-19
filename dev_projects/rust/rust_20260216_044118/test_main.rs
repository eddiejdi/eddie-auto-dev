use reqwest;
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Simulação de uma requisição GET para Jira
    let jira_url = "https://your-jira-instance.atlassian.net/rest/api/2.0/search";
    let query = r#"{
        "jql": "project = YOUR_PROJECT_KEY AND assignee = currentUser() ORDER BY updated DESC",
        "fields": ["key", "summary", "status"]
    }"#;

    // Simulação de uma resposta JSON válida
    let response_json = r#"
    {
        "issues": [
            {"key": "JIRA-123", "summary": "Task 1", "status": "In Progress"},
            {"key": "JIRA-456", "summary": "Task 2", "status": "Completed"}
        ]
    }
    "#;

    // Simulação de uma resposta JSON inválida
    let response_json_invalid = r#"
    {
        "issues": [
            {"key": "JIRA-123", "summary": "Task 1", "status": "In Progress"},
            {"key": "JIRA-456", "summary": "Task 2", "status": "Completed"}
        ]
    }
    "#;

    // Simulação de uma resposta JSON vazia
    let response_json_empty = r#""#;

    // Simulação de uma resposta JSON com erro
    let response_json_error = r#"
    {
        "error": "Invalid query"
    }
    "#;

    // Teste para sucesso com valores válidos
    assert_eq!(
        get_jira_issues(jira_url, query),
        Ok(vec![
            JiraIssue {
                key: "JIRA-123".to_string(),
                summary: "Task 1".to_string(),
                status: "In Progress".to_string()
            },
            JiraIssue {
                key: "JIRA-456".to_string(),
                summary: "Task 2".to_string(),
                status: "Completed".to_string()
            }
        ])
    );

    // Teste para erro (divisão por zero)
    assert_eq!(
        get_jira_issues(jira_url, query),
        Err("Failed to retrieve JIRA issues: HTTP error 400")
    );

    // Teste para erro (valores inválidos)
    assert_eq!(
        get_jira_issues(jira_url, query),
        Err("Failed to retrieve JIRA issues: Invalid JSON response")
    );

    // Teste para edge case (valores limite)
    assert_eq!(
        get_jira_issues(jira_url, query),
        Ok(vec![
            JiraIssue {
                key: "JIRA-123".to_string(),
                summary: "Task 1".to_string(),
                status: "In Progress".to_string()
            },
            JiraIssue {
                key: "JIRA-456".to_string(),
                summary: "Task 2".to_string(),
                status: "Completed".to_string()
            }
        ])
    );

    // Teste para edge case (string vazia)
    assert_eq!(
        get_jira_issues(jira_url, query),
        Err("Failed to retrieve JIRA issues: Empty JSON response")
    );

    // Teste para edge case (None)
    assert_eq!(
        get_jira_issues(jira_url, query),
        Err("Failed to retrieve JIRA issues: None response")
    );

    // Teste para edge case (error)
    assert_eq!(
        get_jira_issues(jira_url, query),
        Err("Failed to retrieve JIRA issues: HTTP error 500")
    );

    Ok(())
}

fn get_jira_issues(url: &str, query: &str) -> Result<Vec<JiraIssue>, Box<dyn std::error::Error>> {
    let response = reqwest::get(url)?
        .header("Content-Type", "application/json")
        .body(query)
        .send()?;

    if response.status().is_success() {
        Ok(serde_json::from_reader(response.text()?)?)
    } else {
        Err(format!("Failed to retrieve JIRA issues: {}", response.status()))
    }
}