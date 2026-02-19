use reqwest;
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
}

async fn fetch_jira_issue(issue_key: &str) -> Result<JiraIssue, Box<dyn std::error::Error>> {
    let client = reqwest::Client::new();
    let response = client.get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key))
        .header("Authorization", "Basic your-base64-encoded-auth")
        .send()?;

    if !response.status().is_success() {
        return Err(format!("Failed to fetch issue: {}", response.status()).into());
    }

    let json = response.text()?;
    Ok serde_json::from_str(&json)?
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Teste de sucesso com valores válidos
    let issue_key = "ABC-123";
    let issue = fetch_jira_issue(issue_key).await?;
    assert_eq!(issue.key, "ABC-123");
    assert_eq!(issue.summary, "Sample Issue");

    // Caso de erro (divisão por zero)
    let invalid_division = 0.0 / 0.0;
    assert!(invalid_division.is_nan());

    // Edge case (valores limite)
    let max_int = i32::MAX as f64;
    let min_float = f64::MIN;

    // Teste de erro (valores inválidos)
    let invalid_key = "ABC";
    let issue = fetch_jira_issue(invalid_key).await;
    assert!(issue.is_err());

    println!("All tests passed!");
    Ok(())
}