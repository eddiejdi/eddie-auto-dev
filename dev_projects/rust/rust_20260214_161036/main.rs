use reqwest;
use serde_json::Value;

struct JiraClient {
    base_url: String,
    token: String,
}

impl JiraClient {
    fn new(base_url: &str, token: &str) -> Self {
        JiraClient {
            base_url: base_url.to_string(),
            token: token.to_string(),
        }
    }

    async fn get_issue(&self, issue_key: &str) -> Result<Value, reqwest::Error> {
        let url = format!("{}rest/api/2/issue/{}", self.base_url, issue_key);
        let headers = [("Authorization", &format!("Bearer {}", self.token))].into_iter().collect();
        reqwest::get(&url).headers(headers).send().await?.json()
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-api-token");

    // Example usage: Get an issue
    let issue_key = "RUST-123";
    let issue = jira_client.get_issue(issue_key).await?;

    println!("Issue details: {:?}", issue);

    Ok(())
}