use reqwest;
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

async fn fetch_jira_issue(issue_key: &str) -> Result<JiraIssue, Box<dyn std::error::Error>> {
    let url = format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key);
    let response = reqwest::get(&url).await?;
    if !response.status().is_success() {
        return Err(format!("Failed to fetch Jira issue: {}", response.text().await?));
    }
    let json: Value = serde_json::from_str(&response.text().await?)?;
    Ok(JiraIssue {
        key: json["key"].as_str().unwrap().to_string(),
        summary: json["fields"]["summary"].as_str().unwrap().to_string(),
        status: json["fields"]["status"]["name"].as_str().unwrap().to_string(),
    })
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let issue_key = "JIRA-123";
    let issue = fetch_jira_issue(issue_key).await?;
    println!("Issue Key: {}", issue.key);
    println!("Summary: {}", issue.summary);
    println!("Status: {}", issue.status);

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_fetch_jira_issue_success() {
        let issue_key = "JIRA-123";
        let response = reqwest::get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key)).await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::OK);
    }

    #[tokio::test]
    async fn test_fetch_jira_issue_failure() {
        let issue_key = "JIRA-123";
        let response = reqwest::get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key)).await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn test_fetch_jira_issue_invalid_json() {
        let issue_key = "JIRA-123";
        let response = reqwest::get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key)).await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn test_fetch_jira_issue_missing_field() {
        let issue_key = "JIRA-123";
        let response = reqwest::get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key)).await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn test_fetch_jira_issue_missing_status() {
        let issue_key = "JIRA-123";
        let response = reqwest::get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key)).await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn test_fetch_jira_issue_missing_key() {
        let issue_key = "JIRA-123";
        let response = reqwest::get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key)).await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn test_fetch_jira_issue_missing_summary() {
        let issue_key = "JIRA-123";
        let response = reqwest::get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key)).await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::BAD_REQUEST);
    }

    #[tokio::test]
    async fn test_fetch_jira_issue_missing_status_name() {
        let issue_key = "JIRA-123";
        let response = reqwest::get(&format!("https://your-jira-instance.atlassian.net/rest/api/2/issue/{}", issue_key)).await.unwrap();
        assert_eq!(response.status(), reqwest::StatusCode::BAD_REQUEST);
    }
}