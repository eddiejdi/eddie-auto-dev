use jira_client::{Client, Error};
use serde_json::Value;

// Define a struct to represent an issue in Jira
#[derive(Debug)]
struct Issue {
    key: String,
    summary: String,
    status: String,
}

impl Issue {
    fn new(key: &str, summary: &str, status: &str) -> Self {
        Issue {
            key: key.to_string(),
            summary: summary.to_string(),
            status: status.to_string(),
        }
    }

    fn to_json(&self) -> Value {
        serde_json::to_value(self).unwrap()
    }
}

// Define a struct to represent the Rust Agent
#[derive(Debug)]
struct RustAgent {
    client: Client,
}

impl RustAgent {
    fn new(api_token: &str, base_url: &str) -> Result<Self, Error> {
        Ok(RustAgent {
            client: Client::new(api_token, base_url),
        })
    }

    async fn get_issue(&self, issue_key: &str) -> Result<Issue, Error> {
        let issue = self.client.issue(issue_key).await?;
        Ok(Issue::from_json(&issue))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize the Rust Agent
    let rust_agent = RustAgent::new("your_api_token", "https://your_jira_instance.atlassian.net")?;

    // Get an issue by key
    let issue_key = "ABC-123";
    let issue = rust_agent.get_issue(issue_key).await?;

    println!("Issue: {:?}", issue);

    Ok(())
}