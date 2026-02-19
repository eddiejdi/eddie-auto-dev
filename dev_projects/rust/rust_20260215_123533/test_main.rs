use reqwest;
use serde_json;

struct JiraClient {
    url: String,
    token: String,
}

impl JiraClient {
    fn new(url: &str, token: &str) -> Self {
        JiraClient {
            url: url.to_string(),
            token: token.to_string(),
        }
    }

    async fn get_issue(&self, issue_key: &str) -> Result<String, reqwest::Error> {
        let response = reqwest::get(format!("{}rest/api/2/issue/{}", self.url, issue_key))
            .header("Authorization", format!("Basic {}", base64::encode(&format!(":{}:{}", self.token, "xss")))) // Base64 encoding of username:password
            .send()
            .await?;

        if response.status().is_success() {
            let body = response.text().await?;
            serde_json::from_str::<serde_json::Value>(&body).map_err(|e| e.into())
        } else {
            Err(response.error_for_status().unwrap().json().await?)
        }
    }

    async fn create_issue(&self, issue_data: &serde_json::Value) -> Result<String, reqwest::Error> {
        let response = reqwest::post(format!("{}rest/api/2/issue", self.url))
            .header("Authorization", format!("Basic {}", base64::encode(&format!(":{}:{}", self.token, "xss")))) // Base64 encoding of username:password
            .json(issue_data)
            .send()
            .await?;

        if response.status().is_success() {
            let body = response.text().await?;
            serde_json::from_str::<serde_json::Value>(&body).map_err(|e| e.into())
        } else {
            Err(response.error_for_status().unwrap().json().await?)
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net/", "your-api-token");

    // Create a new issue
    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR-PROJECT"},
            "summary": "Test Issue",
            "description": "This is a test issue created using Rust and Jira API.",
            "issuetype": {"name": "Task"}
        }
    });

    let response = jira_client.create_issue(&issue_data).await?;
    println!("Issue created: {}", response);

    // Get an existing issue
    let issue_key = "ABC-123";
    let issue_response = jira_client.get_issue(issue_key).await?;
    println!("Issue details: {}", issue_response);

    Ok(())
}