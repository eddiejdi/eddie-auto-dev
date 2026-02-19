use reqwest::Client;
use serde_json::Value;

#[derive(Debug)]
struct JiraIssue {
    key: String,
    summary: String,
    status: String,
}

impl JiraIssue {
    fn new(key: &str, summary: &str, status: &str) -> Self {
        JiraIssue {
            key: key.to_string(),
            summary: summary.to_string(),
            status: status.to_string(),
        }
    }

    fn to_json(&self) -> String {
        serde_json::to_string(self).unwrap()
    }
}

#[derive(Debug)]
struct JiraClient {
    client: Client,
    base_url: String,
}

impl JiraClient {
    fn new(base_url: &str) -> Self {
        JiraClient {
            client: Client::new(),
            base_url: base_url.to_string(),
        }
    }

    async fn get_issue(&self, issue_key: &str) -> Result<JiraIssue, reqwest::Error> {
        let url = format!("{}rest/api/2/issue/{}", self.base_url, issue_key);
        let response = self.client.get(url).send().await?;
        if response.status() == 200 {
            Ok(response.json::<JiraIssue>().await?)
        } else {
            Err(reqwest::Error::from(response))
        }
    }

    async fn update_issue_status(&self, issue_key: &str, status: &str) -> Result<(), reqwest::Error> {
        let url = format!("{}rest/api/2/issue/{}/status", self.base_url, issue_key);
        let payload = serde_json::to_string(&JiraIssue::new(issue_key, "Updated by Rust Agent", status)).unwrap();
        let response = self.client.put(url).body(payload).send().await?;
        if response.status() == 204 {
            Ok(())
        } else {
            Err(reqwest::Error::from(response))
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let jira_client = JiraClient::new("https://your-jira-instance.atlassian.net");

    // Get an issue
    let issue_key = "ABC-123";
    let issue = jira_client.get_issue(issue_key).await?;
    println!("Issue: {:?}", issue);

    // Update the issue status
    let new_status = "In Progress";
    jira_client.update_issue_status(issue_key, &new_status).await?;

    Ok(())
}