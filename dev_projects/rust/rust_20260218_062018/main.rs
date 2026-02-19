use reqwest;
use serde_json::Value;

// Define a struct to represent a Jira issue
struct Issue {
    key: String,
    summary: String,
}

impl Issue {
    fn new(key: &str, summary: &str) -> Self {
        Issue {
            key: key.to_string(),
            summary: summary.to_string(),
        }
    }

    async fn create_issue(&self, jira_url: &str, auth_token: &str) -> Result<(), Box<dyn std::error::Error>> {
        let json = serde_json::json!({
            "fields": {
                "project": {"key": "YOUR_PROJECT_KEY"},
                "summary": self.summary,
                "description": "Automatically created by Rust Agent",
                "issuetype": {"name": "Bug"}
            }
        });

        let response = reqwest::post(format!("{}rest/api/2/issue", jira_url))
            .header("Authorization", format!("Basic {}", auth_token))
            .json(&json)
            .send()
            .await?;

        if response.status().is_success() {
            Ok(())
        } else {
            Err(Box::new(response.text().await.unwrap()))
        }
    }
}

// Define a struct to represent the Rust Agent
struct RustAgent {
    jira_url: String,
    auth_token: String,
}

impl RustAgent {
    fn new(jira_url: &str, auth_token: &str) -> Self {
        RustAgent {
            jira_url: jira_url.to_string(),
            auth_token: auth_token.to_string(),
        }
    }

    async fn monitor_activity(&self, issues: Vec<Issue>) -> Result<(), Box<dyn std::error::Error>> {
        for issue in issues {
            let response = reqwest::get(format!("{}rest/api/2/issue/{}/comment", self.jira_url, issue.key))
                .header("Authorization", format!("Basic {}", self.auth_token))
                .send()
                .await?;

            if response.status().is_success() {
                println!("Comment added to issue {}: {}", issue.key, response.text().await.unwrap());
            } else {
                Err(Box::new(response.text().await.unwrap()))
            }
        }

        Ok(())
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_url = "https://your-jira-instance.atlassian.net";
    let auth_token = "YOUR_AUTH_TOKEN";

    let rust_agent = RustAgent::new(jira_url, auth_token);

    // Create a new issue
    let issue = Issue::new("RUST-123", "Test issue for Rust Agent");
    rust_agent.create_issue(&jira_url, &auth_token).await?;

    // Monitor activity on the created issue
    let issues = vec![issue];
    rust_agent.monitor_activity(issues).await?;

    Ok(())
}