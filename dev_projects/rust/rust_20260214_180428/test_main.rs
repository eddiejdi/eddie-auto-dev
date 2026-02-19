use reqwest;
use serde_json;

// Define a struct to represent the Jira issue
#[derive(Debug, Serialize)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

// Function to create an issue in Jira
async fn create_issue(jira_url: &str, auth_token: &str, issue_data: &Issue) -> Result<(), reqwest::Error> {
    let url = format!("{}/rest/api/2/issue", jira_url);
    let response = reqwest::post(url)
        .header("Authorization", format!("Basic {}", auth_token))
        .json(issue_data)
        .send();

    if response.is_ok() {
        println!("Issue created successfully!");
    } else {
        eprintln!("Failed to create issue: {:?}", response);
    }

    Ok(())
}

// Main function for the CLI app
#[cfg(not(target_arch = "wasm"))]
fn main() {
    // Example usage
    let jira_url = "https://your-jira-instance.atlassian.net";
    let auth_token = "your-auth-token";
    let issue_data = Issue {
        key: "ABC-123".to_string(),
        summary: "New feature request".to_string(),
        status: "To Do".to_string(),
    };

    create_issue(jira_url, auth_token, &issue_data).unwrap();
}

// Test cases for the create_issue function
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_create_issue_success() {
        let jira_url = "https://your-jira-instance.atlassian.net";
        let auth_token = "your-auth-token";
        let issue_data = Issue {
            key: "ABC-123".to_string(),
            summary: "New feature request".to_string(),
            status: "To Do".to_string(),
        };

        create_issue(jira_url, auth_token, &issue_data).await.unwrap();
    }

    #[tokio::test]
    async fn test_create_issue_failure() {
        let jira_url = "https://your-jira-instance.atlassian.net";
        let auth_token = "your-auth-token";
        let issue_data = Issue {
            key: "ABC-123".to_string(),
            summary: "New feature request".to_string(),
            status: "To Do".to_string(),
        };

        create_issue(jira_url, auth_token, &issue_data).await.unwrap_err();
    }
}