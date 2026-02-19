use reqwest;
use serde_json;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_issue(issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    if response.status().is_success() {
        Ok(serde_json::from_str::<JiraIssue>(&response.text().await?)?)
    } else {
        Err(reqwest::Error::new(reqwest::StatusCode::INTERNAL_SERVER_ERROR, "Failed to fetch issue"))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Teste de sucesso com valores válidos
    let issue_key = "RUST-12";
    let issue = fetch_issue(issue_key).await?;
    assert_eq!(issue.key, "RUST-12");
    assert_eq!(issue.summary, "Example Issue");
    assert_eq!(issue.status, "Open");

    // Teste de erro (divisão por zero)
    let invalid_division = 0.0 / 0.0;
    assert_eq!(invalid_division, f64::INFINITY);

    // Teste de erro (valor inválido)
    let invalid_input = "not a number";
    assert_eq!(serde_json::from_str::<JiraIssue>(&invalid_input), Err(serde_json::Error::Syntax));

    Ok(())
}