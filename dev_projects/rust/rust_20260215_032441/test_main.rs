use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

impl JiraIssue {
    fn new(key: &str, summary: &str, status: &str) -> Self {
        JiraIssue {
            key: key.to_string(),
            summary: summary.to_string(),
            status: status.to_string(),
        }
    }

    fn to_json(&self) -> serde_json::Value {
        serde_json::json!({
            "key": self.key,
            "summary": self.summary,
            "status": self.status
        })
    }
}

async fn send_jira_issue(issue: JiraIssue, url: &str) -> Result<(), Box<dyn std::error::Error>> {
    let json = issue.to_json();
    let response = reqwest::post(url)
        .json(json)
        .send()?;

    if response.status().is_success() {
        Ok(())
    } else {
        Err(format!("Failed to send Jira issue: {}", response.text()).into())
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let url = "https://your-jira-instance.atlassian.net/rest/api/2/issue";
    let jira_issue = JiraIssue::new("JIRA-123", "Implement Rust Agent with Jira", "In Progress");

    // Teste de sucesso com valores válidos
    assert_eq!(send_jira_issue(jira_issue.clone(), url).await, Ok(()));

    // Caso de erro (divisão por zero)
    let invalid_json = serde_json::json!({
        "key": "JIRA-123",
        "summary": "Implement Rust Agent with Jira",
        "status": "In Progress"
    });
    assert_eq!(send_jira_issue(JiraIssue::new("JIRA-123", "Implement Rust Agent with Jira", "In Progress"), url).await, Err(format!("Failed to send Jira issue: {}", invalid_json.to_string()).into()));

    // Edge case (valores limite)
    let jira_issue_limit = JiraIssue::new(&"A".repeat(100), &"Implement Rust Agent with Jira", "In Progress");
    assert_eq!(send_jira_issue(jira_issue_limit.clone(), url).await, Ok(()));

    // Edge case (string vazia)
    let jira_issue_empty = JiraIssue::new("", "", "");
    assert_eq!(send_jira_issue(jira_issue_empty.clone(), url).await, Err(format!("Failed to send Jira issue: {}", jira_issue_empty.to_string()).into()));

    println!("All tests passed!");

    Ok(())
}