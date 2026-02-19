use reqwest;
use serde_json::Value;

struct Jira {
    url: String,
    auth_token: String,
}

impl Jira {
    fn new(url: &str, auth_token: &str) -> Self {
        Jira {
            url: url.to_string(),
            auth_token: auth_token.to_string(),
        }
    }

    async fn create_issue(&self, issue_data: Value) -> Result<(), reqwest::Error> {
        let response = reqwest::post(&self.url)
            .header("Content-Type", "application/json")
            .header("Authorization", format!("Basic {}", self.auth_token))
            .body(issue_data.to_string())
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(reqwest::Error::from(response.text().await.unwrap()))
        }
    }

    async fn get_issues(&self) -> Result<Vec<Value>, reqwest::Error> {
        let response = reqwest::get(&format!("{}rest/api/2/search", self.url))
            .header("Content-Type", "application/json")
            .header("Authorization", format!("Basic {}", self.auth_token))
            .send()
            .await?;

        if response.status().is_success() {
            serde_json::from_str(&response.text().await.unwrap()).unwrap()
        } else {
            Err(reqwest::Error::from(response.text().await.unwrap()))
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira = Jira::new("https://your-jira-instance.atlassian.net/rest/api/2/", "your-auth-token");

    // Create a new issue
    let issue_data = serde_json::json!({
        "fields": {
            "project": {"key": "YOUR-PROJECT"},
            "summary": "Test issue",
            "description": "This is a test issue created by Rust Agent",
            "issuetype": {"name": "Bug"}
        }
    });

    jira.create_issue(issue_data).await?;

    // Get all issues
    let issues = jira.get_issues().await?;
    println!("Issues: {:?}", issues);

    Ok(())
}