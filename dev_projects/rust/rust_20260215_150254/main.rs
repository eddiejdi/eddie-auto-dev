use reqwest;
use serde_json::Value;

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

    async fn create_issue(&self, issue_data: Value) -> Result<Value, reqwest::Error> {
        let response = reqwest::post(&format!("{}rest/api/2/issue", self.url))
            .header("Authorization", format!("Basic {}", base64::encode(format!(":{}:{}", self.token, "xss"))))
            .json(issue_data)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(response.json().await?)
        } else {
            Err(reqwest::Error::from(response.text().await.unwrap()))
        }
    }

    async fn get_issues(&self, query: &str) -> Result<Vec<Value>, reqwest::Error> {
        let response = reqwest::get(&format!("{}rest/api/2/search?jql={}", self.url, query))
            .header("Authorization", format!("Basic {}", base64::encode(format!(":{}:{}", self.token, "xss"))))
            .send()
            .await?;

        if response.status().is_success() {
            Ok(response.json().await?)
        } else {
            Err(reqwest::Error::from(response.text().await.unwrap()))
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), reqwest::Error> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net/", "your-api-token");

    // Create an issue
    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR_PROJECT_KEY"},
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent",
            "issuetype": {"name": "Bug"}
        }
    });

    let created_issue = jira_client.create_issue(issue_data).await?;
    println!("Created Issue: {:?}", created_issue);

    // Get issues
    let query = "project=YOUR_PROJECT_KEY AND status!=closed";
    let issues = jira_client.get_issues(query).await?;

    for issue in issues {
        println!("Issue: {:?}", issue);
    }

    Ok(())
}