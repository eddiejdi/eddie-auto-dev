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

    async fn create_issue(&self, issue_data: Value) -> Result<String, reqwest::Error> {
        let response = self
            .client()
            .post(format!("{}rest/api/2/issue", &self.url))
            .header("Authorization", format!("Basic {}", base64::encode(&format!(":{}:", self.token))))
            .json(issue_data)
            .send()
            .await?;

        if response.status().is_success() {
            let json = response.json::<Value>().await?;
            Ok(json["id"].as_str().unwrap().to_string())
        } else {
            Err(reqwest::Error::from(response))
        }
    }

    fn client(&self) -> reqwest::Client {
        reqwest::Client::new()
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net", "your-api-token");

    let issue_data = json!({
        "fields": {
            "project": { "key": "YOUR-PROJECT" },
            "summary": "Test Issue",
            "description": "This is a test issue created by Rust Agent",
            "issuetype": { "name": "Bug" }
        }
    });

    let issue_id = jira_client.create_issue(issue_data).await?;
    println!("Issue created with ID: {}", issue_id);

    Ok(())
}