use reqwest;
use serde_json;

#[derive(serde::Deserialize)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn get_jira_issue(issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    response.json().await
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let issue_key = "JIRA-123";
    let jira_issue = get_jira_issue(issue_key).await?;

    println!("Issue Key: {}", jira_issue.key);
    println!("Summary: {}", jira_issue.summary);
    println!("Status: {}", jira_issue.status);

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_get_jira_issue_success() {
        let issue_key = "JIRA-123";
        let response = get_jira_issue(issue_key).await.unwrap();
        assert_eq!(response.key, "JIRA-123");
        assert_eq!(response.summary, "Test Issue");
        assert_eq!(response.status, "Open");
    }

    #[tokio::test]
    async fn test_get_jira_issue_error() {
        let issue_key = "JIRA-456";
        match get_jira_issue(issue_key).await {
            Ok(_) => panic!("Expected an error"),
            Err(e) => assert_eq!(e.status(), reqwest::StatusCode::NOT_FOUND),
        }
    }

    #[tokio::test]
    async fn test_get_jira_issue_edge_case() {
        let issue_key = "";
        match get_jira_issue(issue_key).await {
            Ok(_) => panic!("Expected an error"),
            Err(e) => assert_eq!(e.status(), reqwest::StatusCode::BAD_REQUEST),
        }
    }

    #[tokio::test]
    async fn test_get_jira_issue_none() {
        let issue_key = None;
        match get_jira_issue(issue_key).await {
            Ok(_) => panic!("Expected an error"),
            Err(e) => assert_eq!(e.status(), reqwest::StatusCode::BAD_REQUEST),
        }
    }

    #[tokio::test]
    async fn test_get_jira_issue_division_by_zero() {
        let issue_key = "JIRA-789";
        match get_jira_issue(issue_key).await {
            Ok(_) => panic!("Expected an error"),
            Err(e) => assert_eq!(e.status(), reqwest::StatusCode::BAD_REQUEST),
        }
    }

    #[tokio::test]
    async fn test_get_jira_issue_invalid_json() {
        let issue_key = "JIRA-012";
        match get_jira_issue(issue_key).await {
            Ok(_) => panic!("Expected an error"),
            Err(e) => assert_eq!(e.status(), reqwest::StatusCode::BAD_REQUEST),
        }
    }
}