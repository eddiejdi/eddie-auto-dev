use reqwest;
use serde_json::Value;

// Define a struct to represent an issue in Jira
struct Issue {
    key: String,
    summary: String,
    status: String,
}

// Define a struct to represent the response from Jira API
struct JiraResponse {
    issues: Vec<Issue>,
}

async fn fetch_jira_issues(jira_url: &str, auth_token: &str) -> Result<JiraResponse, reqwest::Error> {
    let url = format!("{}rest/api/2/search?jql=status!=Closed", jira_url);
    let headers = [("Authorization", format!("Bearer {}", auth_token).as_str())];
    let response = reqwest::get(&url, &headers)
        .await?
        .json::<JiraResponse>()
        .await?;
    Ok(response)
}

async fn update_issue_status(jira_url: &str, issue_key: &str, new_status: &str, auth_token: &str) -> Result<(), reqwest::Error> {
    let url = format!("{}rest/api/2/issue/{}/status", jira_url, issue_key);
    let headers = [("Authorization", format!("Bearer {}", auth_token).as_str())];
    let payload = serde_json::json!({
        "update": {
            "fields": {
                "status": {
                    "id": new_status
                }
            }
        }
    });
    reqwest::put(&url, &headers)
        .body(payload.to_string())
        .send()
        .await?;
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net";
    let auth_token = "your-auth-token";

    // Fetch issues
    let response = fetch_jira_issues(jira_url, auth_token).await?;
    for issue in response.issues {
        println!("Issue: {}", issue.key);
        println!("Summary: {}", issue.summary);
        println!("Status: {}", issue.status);
        println!();
    }

    // Update status of an issue
    let issue_key = "ABC-123";
    let new_status = "In Progress";
    update_issue_status(jira_url, issue_key, new_status, auth_token).await?;

    Ok(())
}