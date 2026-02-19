use reqwest;
use serde_json;

struct JiraClient {
    url: String,
    auth_token: String,
}

impl JiraClient {
    fn new(url: String, auth_token: String) -> Self {
        JiraClient { url, auth_token }
    }

    async fn create_issue(&self, project_key: &str, summary: &str, description: &str) -> Result<(), reqwest::Error> {
        let issue_data = serde_json!({
            "fields": {
                "project": {
                    "key": project_key
                },
                "summary": summary,
                "description": description,
                "issuetype": {
                    "name": "Bug"
                }
            }
        });

        let response = reqwest::post(&self.url)
            .header("Authorization", &format!("Basic {}", base64::encode(format!("{}:{}", self.auth_token, ""))))
            .json(issue_data)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::from(response))
        }
    }

    async fn get_issues(&self) -> Result<Vec<serde_json::Value>, reqwest::Error> {
        let response = reqwest::get(&format!("{}rest/api/2/search", self.url))
            .header("Authorization", &format!("Basic {}", base64::encode(format!("{}:{}", self.auth_token, ""))))
            .send()
            .await?;

        if response.status().is_success() {
            let json = response.json::<serde_json::Value>().await?;
            serde_json::from_value(json["issues"].clone())
        } else {
            Err(reqwest::Error::from(response))
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net/rest/api/2/", "your-auth-token");

    // Create a new issue
    jira_client.create_issue("YOUR-PROJECT", "Bug in Rust Agent", "This is a test bug for the Rust Agent.").await?;

    // Get all issues
    let issues = jira_client.get_issues().await?;
    println!("Issues: {:?}", issues);

    Ok(())
}